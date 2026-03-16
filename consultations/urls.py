from django.urls import path
from . import views

app_name = 'consultations'

urlpatterns = [
    path('', views.ConsultationListView.as_view(), name='consultation_list'),
    path('book/', views.ConsultationCreateView.as_view(), name='consultation_create'),
    path('<int:pk>/edit/', views.ConsultationUpdateView.as_view(), name='consultation_update'),
    path('<int:pk>/delete/', views.delete_consultation, name='consultation_delete'),
    path('<int:pk>/complete/', views.mark_complete, name='consultation_complete'),
]
