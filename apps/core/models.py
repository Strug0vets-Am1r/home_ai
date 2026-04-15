from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Расширенная модель пользователя"""
    has_dishwasher = models.BooleanField(null=True, blank=True)
    has_robot_vacuum = models.BooleanField(null=True, blank=True)
    room_count = models.PositiveSmallIntegerField(null=True, blank=True)
    has_plants = models.BooleanField(null=True, blank=True)
    has_pets = models.BooleanField(null=True, blank=True)
    cleaning_frequency = models.CharField(
        max_length=20,
        choices=[('daily', 'Ежедневно'), ('weekly', 'Еженедельно'), ('monthly', 'Ежемесячно')],
        null=True,
        blank=True
    )
    is_survey_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class Task(models.Model):
    """Модель задачи"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks'
    )

    def __str__(self):
        return self.title


class TaskHistory(models.Model):
    """История выполнения задач"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task_title = models.CharField(max_length=255)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.task_title} - {self.completed_at}"