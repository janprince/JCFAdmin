from django.urls import path
from . import views

app_name = 'resources'

urlpatterns = [
    path('', views.ResourceListView.as_view(), name='resource_list'),
    path('add/', views.ResourceCreateView.as_view(), name='resource_create'),
    path('<int:pk>/edit/', views.ResourceUpdateView.as_view(), name='resource_update'),
    path('<int:pk>/delete/', views.ResourceDeleteView.as_view(), name='resource_delete'),
]
