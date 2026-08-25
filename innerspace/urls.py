from django.urls import path

from . import views

app_name = 'innerspace'

urlpatterns = [
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('students/<str:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('students/<str:pk>/grant/', views.GrantAccessView.as_view(), name='grant_access'),
    path('students/<str:pk>/extend/', views.ExtendAccessView.as_view(), name='extend_access'),
    path('students/<str:pk>/revoke/', views.RevokeAccessView.as_view(), name='revoke_access'),
]
