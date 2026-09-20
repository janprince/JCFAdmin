from django.urls import path

from . import views

app_name = 'practices'

urlpatterns = [
    path('', views.PracticeListView.as_view(), name='practice_list'),
    path('add/', views.PracticeCreateView.as_view(), name='practice_create'),
    path('<int:pk>/edit/', views.PracticeUpdateView.as_view(), name='practice_update'),
]
