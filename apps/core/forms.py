import datetime

from django import forms
from django.utils import timezone
from .models import Task, User, Category


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date', 'category', 'is_favorite', 'task_list']
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
            'category': forms.Select(attrs={'class': 'select'}),
            'is_favorite': forms.CheckboxInput(),
            'task_list': forms.HiddenInput(),
        }
        labels = {
            'title': 'Название задачи',
            'description': 'Описание',
            'due_date': 'Дата и время выполнения',
            'category': 'Категория',
            'is_favorite': 'Добавить в избранное',
            'task_list': 'Список',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['category'].queryset = Category.objects.filter(user=user)
        else:
            self.fields['category'].queryset = Category.objects.none()
        self.fields['category'].required = False
        self.fields['category'].empty_label = 'Без категории'

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
        now = timezone.localtime().replace(second=0, microsecond=0)

        if not due_date:
            minutes = now.minute
            remainder = minutes % 5
            delta = (5 - remainder) if remainder else 5
            due_date = now + datetime.timedelta(minutes=delta)
            return due_date

        due_date_local = timezone.localtime(due_date)
        if due_date_local <= now:
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
            'room_count': 'Количество комнат',
            'cleaning_frequency': 'Частота уборки',
            'has_dishwasher': 'Посудомоечная машина',
            'has_robot_vacuum': 'Робот-пылесос',
            'has_plants': 'Есть растения',
            'has_pets': 'Есть питомцы',
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Название категории'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'category-color-input'}),
        }
        labels = {
            'name': 'Название',
            'color': 'Цвет',
        }