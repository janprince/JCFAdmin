from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.StaffListView.as_view(), name='staff_list'),
    path('add/', views.StaffCreateView.as_view(), name='staff_create'),
    path('<int:pk>/edit/', views.StaffUpdateView.as_view(), name='staff_update'),
]
