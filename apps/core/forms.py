from django import forms
from django.utils import timezone
from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date']
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
        }
        labels = {
            'title': 'Название задачи',
            'description': 'Описание',
            'due_date': 'Дата и время выполнения',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        now = timezone.localtime().replace(second=0, microsecond=0)
        now_str = now.strftime('%Y-%m-%dT%H:%M')

        self.fields['due_date'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['title'].widget.attrs['class'] = 'form-control'
        self.fields['description'].widget.attrs['class'] = 'form-control'
        self.fields['due_date'].widget.attrs['class'] = 'form-control'
        self.fields['due_date'].widget.attrs['min'] = now_str

        if self.instance and self.instance.pk and self.instance.due_date:
            local_due_date = timezone.localtime(self.instance.due_date).replace(second=0, microsecond=0)
            self.initial['due_date'] = local_due_date.strftime('%Y-%m-%dT%H:%M')
        else:
            self.initial['due_date'] = now_str