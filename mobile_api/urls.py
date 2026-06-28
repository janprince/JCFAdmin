"""Mobile app API — versioned namespace mounted at /api/mobile/v1/."""
from django.urls import path

from . import views
from . import content
from . import payments
from . import programs_api
from . import engagement_api

app_name = 'mobile_api'

urlpatterns = [
    # Auth
    path('auth/request-code/', views.RequestCodeView.as_view(), name='request_code'),
    path('auth/verify-code/', views.VerifyCodeView.as_view(), name='verify_code'),
    path('auth/refresh/', views.RefreshView.as_view(), name='refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),

    # Content — teachings (lessons) + series
    path('teachings/', content.TeachingListView.as_view(), name='teaching_list'),
    path('teachings/<slug:slug>/', content.TeachingDetailView.as_view(), name='teaching_detail'),
    path('series/', content.SeriesListView.as_view(), name='series_list'),
    path('series/<slug:slug>/', content.SeriesDetailView.as_view(), name='series_detail'),

    # Payments — causes + Paystack donations
    path('payments/config/', payments.PaymentConfigView.as_view(), name='payment_config'),
    path('causes/', payments.CauseListView.as_view(), name='cause_list'),
    path('causes/<slug:slug>/', payments.CauseDetailView.as_view(), name='cause_detail'),
    path('donations/verify/', payments.DonationVerifyView.as_view(), name='donation_verify'),
    path('donations/mine/', payments.MyDonationsView.as_view(), name='my_donations'),

    # Programs + registration
    path('programs/', programs_api.ProgramListView.as_view(), name='program_list'),
    path('programs/<slug:slug>/', programs_api.ProgramDetailView.as_view(), name='program_detail'),
    path('programs/<slug:slug>/register/', programs_api.RegisterView.as_view(), name='program_register'),
    path('registrations/mine/', programs_api.MyRegistrationsView.as_view(), name='my_registrations'),
    path('registrations/<str:reference>/verify/', programs_api.VerifyRegistrationView.as_view(), name='registration_verify'),

    # Engagement — announcements, push devices, notifications, appointments
    path('announcements/', engagement_api.AnnouncementListView.as_view(), name='announcement_list'),
    path('devices/register/', engagement_api.DeviceRegisterView.as_view(), name='device_register'),
    path('devices/<str:token>/', engagement_api.DeviceUnregisterView.as_view(), name='device_unregister'),
    path('notifications/', engagement_api.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/read/', engagement_api.NotificationReadView.as_view(), name='notification_read'),
    path('appointments/', engagement_api.AppointmentListView.as_view(), name='appointment_list'),
    path('appointments/book/', engagement_api.AppointmentCreateView.as_view(), name='appointment_book'),
]
