from django.urls import path
from . import views

app_name = 'members'

urlpatterns = [
    path('', views.ContactListView.as_view(), name='contact_list'),
    path('members/', views.MemberListView.as_view(), name='member_list'),
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('add/', views.ContactCreateView.as_view(), name='contact_create'),
    path('<int:pk>/', views.ContactDetailView.as_view(), name='contact_detail'),
    path('<int:pk>/edit/', views.ContactUpdateView.as_view(), name='contact_update'),
    path('<int:pk>/delete/', views.ContactDeleteView.as_view(), name='contact_delete'),
    path('<int:pk>/files/', views.add_datafiles, name='add_datafiles'),
    path('files/<int:pk>/delete/', views.delete_datafile, name='delete_datafile'),
    # Inquiries
    path('inquiries/add/<int:contact_pk>/', views.add_inquiry, name='add_inquiry'),
    path('inquiries/<int:pk>/edit/', views.update_inquiry, name='update_inquiry'),
    path('inquiries/<int:pk>/delete/', views.delete_inquiry, name='delete_inquiry'),
]
