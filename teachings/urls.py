from django.urls import path
from . import views

app_name = 'teachings'

urlpatterns = [
    path('', views.TeachingListView.as_view(), name='teaching_list'),
    path('add/', views.TeachingCreateView.as_view(), name='teaching_create'),
    path('<int:pk>/edit/', views.TeachingUpdateView.as_view(), name='teaching_update'),
]
