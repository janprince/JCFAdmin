from django.urls import path

from . import views

app_name = 'programs'

urlpatterns = [
    path('', views.ProgramListView.as_view(), name='program_list'),
    path('add/', views.ProgramCreateView.as_view(), name='program_create'),
    path('<int:pk>/', views.ProgramDetailView.as_view(), name='program_detail'),
    path('<int:pk>/edit/', views.ProgramUpdateView.as_view(), name='program_update'),
    path('<int:pk>/tiers/add/', views.tier_add, name='tier_add'),
    path('tiers/<int:pk>/delete/', views.tier_delete, name='tier_delete'),
    path('<int:pk>/fees/add/', views.cost_item_add, name='cost_item_add'),
    path('fees/<int:pk>/delete/', views.cost_item_delete, name='cost_item_delete'),
    path('registrations/<int:pk>/cancel/', views.registration_cancel, name='registration_cancel'),
]
