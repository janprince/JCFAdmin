from django.urls import path
from . import views

app_name = 'consultations'

urlpatterns = [
    path('', views.ConsultationListView.as_view(), name='consultation_list'),
    path('book/', views.ConsultationCreateView.as_view(), name='consultation_create'),
    path('<int:pk>/edit/', views.ConsultationUpdateView.as_view(), name='consultation_update'),
    path('<int:pk>/delete/', views.delete_consultation, name='consultation_delete'),
    path('<int:pk>/complete/', views.mark_complete, name='consultation_complete'),
    path('requests/', views.RequestListView.as_view(), name='request_list'),
    path('requests/<int:pk>/', views.RequestDetailView.as_view(), name='request_detail'),
    path('requests/<int:pk>/close/', views.RequestActionView.as_view(), {'action': 'close'}, name='request_close'),
    path('requests/<int:pk>/reopen/', views.RequestActionView.as_view(), {'action': 'reopen'}, name='request_reopen'),
    path('requests/<int:pk>/remove/', views.RequestActionView.as_view(), {'action': 'spam'}, name='request_remove'),
]
