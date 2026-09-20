from django.urls import path

from . import views

app_name = 'activities'

urlpatterns = [
    path('', views.ActivityListView.as_view(), name='activity_list'),
    path('add/', views.ActivityCreateView.as_view(), name='activity_create'),
    path('<int:pk>/edit/', views.ActivityUpdateView.as_view(), name='activity_update'),
]
