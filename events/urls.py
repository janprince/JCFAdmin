from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.EventListView.as_view(), name='event_list'),
    path('add/', views.EventCreateView.as_view(), name='event_create'),
    path('<int:pk>/edit/', views.EventUpdateView.as_view(), name='event_update'),
    path('<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    path('categories/', views.EventCategoryListView.as_view(), name='category_list'),
    path('categories/<int:pk>/delete/', views.delete_category, name='category_delete'),
]
