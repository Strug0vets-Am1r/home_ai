from django.contrib import admin
from django.urls import path
from apps.core import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.home, name='home'),
    path('calendar/', views.calendar, name='calendar'),

    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('survey/', views.survey, name='survey'),

    path('task/create/', views.task_create, name='task_create'),
    path('task/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('task/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('task/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    path('tasks/clear-completed/', views.clear_completed_tasks, name='clear_completed_tasks'),

    path('task/create-with-ai/', views.task_create_with_ai, name='task_create_with_ai'),
    path('task/<int:task_id>/generate-subtasks/', views.generate_subtasks_view, name='generate_subtasks_view'),

    path('api/tasks/', views.api_tasks, name='api_tasks'),
    path('api/generate-subtasks/', views.api_generate_subtasks, name='api_generate_subtasks'),
]