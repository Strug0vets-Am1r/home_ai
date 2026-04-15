from django.contrib import admin
from django.urls import path

from apps.core import views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('survey/', views.survey, name='survey'),
    path('', views.home, name='home'),
    path('complete/<int:task_id>/', views.complete_task, name='complete_task'),
    path('task/create/', views.task_create, name='task_create'),
    path('task/edit/<int:task_id>/', views.task_edit, name='task_edit'),
    path('task/delete/<int:task_id>/', views.task_delete, name='task_delete'),
    path('calendar/', views.calendar, name='calendar'),
    path('api/tasks/', views.api_tasks, name='api_tasks'),
    path('task/create-with-ai/', views.task_create_with_ai, name='task_create_with_ai'),
    path('api/generate-subtasks/', views.api_generate_subtasks, name='api_generate_subtasks'),
]