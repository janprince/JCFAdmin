from django.urls import path

from . import views

app_name = 'groups'

urlpatterns = [
    path('', views.GroupListView.as_view(), name='group_list'),
    path('add/', views.GroupCreateView.as_view(), name='group_create'),
    path('<int:pk>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('<int:pk>/edit/', views.GroupUpdateView.as_view(), name='group_update'),
    path('memberships/<int:pk>/approve/', views.approve_membership, name='membership_approve'),
    path('memberships/<int:pk>/decline/', views.decline_membership, name='membership_decline'),
    path('memberships/<int:pk>/remove/', views.remove_membership, name='membership_remove'),
]
