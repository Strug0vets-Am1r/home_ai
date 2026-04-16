from django import forms
from django.utils import timezone
from .models import Task



class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date']
        widgets = {
            'due_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'description': forms.Textarea(attrs={'rows': 3}),
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

        if not self.instance or not self.instance.pk:
            self.initial['due_date'] = now_str