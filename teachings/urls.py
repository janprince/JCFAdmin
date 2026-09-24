from django.urls import path
from . import views

app_name = 'teachings'

urlpatterns = [
    path('', views.TeachingListView.as_view(), name='teaching_list'),
    path('add/', views.TeachingCreateView.as_view(), name='teaching_create'),
    path('<int:pk>/edit/', views.TeachingUpdateView.as_view(), name='teaching_update'),
    path('series/', views.SeriesListView.as_view(), name='series_list'),
    path('series/add/', views.SeriesCreateView.as_view(), name='series_create'),
    path('series/<int:pk>/edit/', views.SeriesUpdateView.as_view(), name='series_update'),
]
