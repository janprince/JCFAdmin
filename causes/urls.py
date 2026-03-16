from django.urls import path
from . import views

app_name = 'causes'

urlpatterns = [
    # Causes
    path('', views.CauseListView.as_view(), name='cause_list'),
    path('add/', views.CauseCreateView.as_view(), name='cause_create'),
    path('<int:pk>/', views.CauseDetailView.as_view(), name='cause_detail'),
    path('<int:pk>/edit/', views.CauseUpdateView.as_view(), name='cause_update'),
    path('<int:pk>/delete/', views.CauseDeleteView.as_view(), name='cause_delete'),

    # Donations
    path('donations/', views.DonationListView.as_view(), name='donation_list'),
    path('donations/add/', views.DonationCreateView.as_view(), name='donation_create'),
    path('donations/<int:pk>/edit/', views.DonationUpdateView.as_view(), name='donation_update'),
    path('donations/<int:pk>/delete/', views.DonationDeleteView.as_view(), name='donation_delete'),
]
