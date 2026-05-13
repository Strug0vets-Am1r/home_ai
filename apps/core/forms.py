import datetime
import zoneinfo

from django import forms
from django.utils import timezone
from .models import Task, User


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date', 'is_favorite', 'task_list']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Например: Приготовить пасту с креветками'}),
            'due_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'description': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'При желании добавь детали: ингредиенты, комнату, условия, приоритеты и т.д.'
                }
            ),
            'is_favorite': forms.CheckboxInput(),
            'task_list': forms.HiddenInput(),
        }
        labels = {
            'title': 'Название задачи',
            'description': 'Описание',
            'due_date': 'Дата и время выполнения',
            'is_favorite': 'Добавить в избранное',
            'task_list': 'Список',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['browser_timezone'] = forms.CharField(
            required=False, widget=forms.HiddenInput()
        )

        now = timezone.localtime().replace(second=0, microsecond=0)
        now_str = now.strftime('%Y-%m-%dT%H:%M')

        remainder = now.minute % 5
        delta = (5 - remainder) if remainder else 5
        rounded = now + datetime.timedelta(minutes=delta)
        rounded_str = rounded.strftime('%Y-%m-%dT%H:%M')

        self.fields['due_date'].required = False
        self.fields['due_date'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['title'].widget.attrs['class'] = 'form-control'
        self.fields['description'].widget.attrs['class'] = 'form-control'
        self.fields['due_date'].widget.attrs['class'] = 'form-control'
        self.fields['due_date'].widget.attrs['min'] = now_str

        if self.instance and self.instance.pk and self.instance.due_date:
            local_due_date = timezone.localtime(self.instance.due_date).replace(second=0, microsecond=0)
            self.initial['due_date'] = local_due_date.strftime('%Y-%m-%dT%H:%M')
        else:
            self.initial['due_date'] = rounded_str

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        browser_tz = self.data.get('browser_timezone') or self.initial.get('browser_timezone')
        now_aware = timezone.localtime().replace(second=0, microsecond=0)

        if not due_date:
            minutes = now_aware.minute
            remainder = minutes % 5
            delta = (5 - remainder) if remainder else 5
            due_date = now_aware + datetime.timedelta(minutes=delta)
            return due_date

        if timezone.is_naive(due_date):
            if browser_tz:
                try:
                    tz = zoneinfo.ZoneInfo(browser_tz)
                    due_date = timezone.make_aware(due_date, tz)
                except (zoneinfo.ZoneInfoNotFoundError, TypeError):
                    due_date = timezone.make_aware(due_date)
            else:
                due_date = timezone.make_aware(due_date)
        else:
            if browser_tz:
                try:
                    tz = zoneinfo.ZoneInfo(browser_tz)
                    naive = due_date.replace(tzinfo=None)
                    due_date = timezone.make_aware(naive, tz)
                except (zoneinfo.ZoneInfoNotFoundError, TypeError):
                    pass

        if timezone.localtime(due_date) <= now_aware:
            raise forms.ValidationError('Дата выполнения не может быть в прошлом. Выбери актуальную дату.')

        return due_date


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'gender',
            'room_count', 'cleaning_frequency',
            'has_dishwasher', 'has_robot_vacuum', 'has_plants', 'has_pets',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Фамилия'}),
            'email': forms.EmailInput(attrs={'class': 'input'}),
            'gender': forms.Select(attrs={'class': 'select'}),
            'room_count': forms.NumberInput(attrs={'class': 'input', 'min': 1, 'max': 20}),
            'cleaning_frequency': forms.Select(attrs={'class': 'select'}),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Email',
            'gender': 'Пол',
            'timezone': 'Часовой пояс',
            'room_count': 'Количество комнат',
            'cleaning_frequency': 'Частота уборки',
            'has_dishwasher': 'Посудомоечная машина',
            'has_robot_vacuum': 'Робот-пылесос',
            'has_plants': 'Есть растения',
            'has_pets': 'Есть питомцы',
        }
