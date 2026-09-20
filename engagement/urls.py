from django.urls import path

from . import views

app_name = 'engagement'

urlpatterns = [
    path('announcements/', views.AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/add/', views.AnnouncementCreateView.as_view(), name='announcement_create'),
    path('announcements/<int:pk>/edit/', views.AnnouncementUpdateView.as_view(), name='announcement_update'),
    path('announcements/<int:pk>/delete/', views.announcement_delete, name='announcement_delete'),
    path('announcements/<int:pk>/pin/', views.announcement_toggle_pin, name='announcement_pin'),
    path('notifications/compose/', views.NotificationComposeView.as_view(), name='notification_compose'),
]
