from django.urls import path
from . import views, access_views

app_name = 'staff'

urlpatterns = [
    path('access/', access_views.UserListView.as_view(), name='user_list'),
    path('access/roles/', access_views.RoleGuideView.as_view(), name='role_guide'),
    path('access/add/', access_views.UserCreateView.as_view(), name='user_create'),
    path('access/<int:pk>/', access_views.UserUpdateView.as_view(), name='user_update'),
    path('access/<int:pk>/password/', access_views.UserPasswordView.as_view(), name='user_password'),
    path('access/<int:pk>/activate/', access_views.UserStatusView.as_view(), {'action': 'activate'}, name='user_activate'),
    path('access/<int:pk>/deactivate/', access_views.UserStatusView.as_view(), {'action': 'deactivate'}, name='user_deactivate'),
    path('', views.StaffListView.as_view(), name='staff_list'),
    path('add/', views.StaffCreateView.as_view(), name='staff_create'),
    path('<int:pk>/edit/', views.StaffUpdateView.as_view(), name='staff_update'),
]
