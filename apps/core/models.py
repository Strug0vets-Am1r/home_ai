from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    has_dishwasher = models.BooleanField(default=False)
    has_robot_vacuum = models.BooleanField(default=False)
    has_plants = models.BooleanField(default=False)
    has_pets = models.BooleanField(default=False)

    CLEANING_FREQUENCY_CHOICES = [
        ('daily', 'Ежедневно'),
        ('weekly', 'Еженедельно'),
        ('monthly', 'Ежемесячно'),
    ]
    cleaning_frequency = models.CharField(
        max_length=20,
        choices=CLEANING_FREQUENCY_CHOICES,
        blank=True,
        null=True
    )

    room_count = models.IntegerField(default=1)
    is_survey_completed = models.BooleanField(default=False)

    GENDER_CHOICES = [
        ('male', 'Мужской'),
        ('female', 'Женский'),
        ('other', 'Другой'),
    ]
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)

    def __str__(self):
        return self.username


class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#6366f1')

    class Meta:
        ordering = ['name']
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name


class Task(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateTimeField()
    is_completed = models.BooleanField(default=False)

    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )

    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['is_completed', 'due_date', 'id']

    def __str__(self):
        return self.title

    @property
    def is_subtask(self):
        return self.parent_task is not None


class TaskHistory(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_history'
    )
    task_title = models.CharField(max_length=255)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f'{self.task_title} - {self.completed_at:%d.%m.%Y %H:%M}'