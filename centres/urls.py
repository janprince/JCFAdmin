from django.urls import path
from . import views

app_name = 'centres'

urlpatterns = [
    path('', views.CentreListView.as_view(), name='centre_list'),
    path('add/', views.CentreCreateView.as_view(), name='centre_create'),
    path('<int:pk>/edit/', views.CentreUpdateView.as_view(), name='centre_update'),
    path('<int:pk>/delete/', views.CentreDeleteView.as_view(), name='centre_delete'),
]
