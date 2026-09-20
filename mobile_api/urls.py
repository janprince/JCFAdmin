"""Mobile app API — versioned namespace mounted at /api/mobile/v1/."""
from django.urls import path

from . import views
from . import content
from . import payments
from . import programs_api
from . import engagement_api
from . import groups_api
from . import practices_api
from . import activities_api

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
    path('teachings/<slug:slug>/progress/', content.TeachingProgressView.as_view(), name='teaching_progress'),
    path('learning/continue/', content.ContinueLearningView.as_view(), name='continue_learning'),
    path('series/', content.SeriesListView.as_view(), name='series_list'),
    path('series/<slug:slug>/', content.SeriesDetailView.as_view(), name='series_detail'),

    # Payments — causes + Paystack donations
    path('payments/config/', payments.PaymentConfigView.as_view(), name='payment_config'),
    path('causes/', payments.CauseListView.as_view(), name='cause_list'),
    path('causes/<slug:slug>/', payments.CauseDetailView.as_view(), name='cause_detail'),
    path('donations/initialize/', payments.DonationInitializeView.as_view(), name='donation_initialize'),
    path('donations/verify/', payments.DonationVerifyView.as_view(), name='donation_verify'),
    path('donations/mine/', payments.MyDonationsView.as_view(), name='my_donations'),

    # Programs + registration
    path('programs/', programs_api.ProgramListView.as_view(), name='program_list'),
    path('programs/<slug:slug>/', programs_api.ProgramDetailView.as_view(), name='program_detail'),
    path('programs/<slug:slug>/register/', programs_api.RegisterView.as_view(), name='program_register'),
    path('registrations/mine/', programs_api.MyRegistrationsView.as_view(), name='my_registrations'),
    path('registrations/<str:reference>/initialize/', programs_api.InitializeRegistrationPaymentView.as_view(), name='registration_initialize'),
    path('registrations/<str:reference>/verify/', programs_api.VerifyRegistrationView.as_view(), name='registration_verify'),

    # Engagement — announcements, push devices, notifications, appointments
    path('announcements/', engagement_api.AnnouncementListView.as_view(), name='announcement_list'),
    path('devices/register/', engagement_api.DeviceRegisterView.as_view(), name='device_register'),
    path('devices/<str:token>/', engagement_api.DeviceUnregisterView.as_view(), name='device_unregister'),
    path('notifications/', engagement_api.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/read/', engagement_api.NotificationReadView.as_view(), name='notification_read'),
    path('appointments/', engagement_api.AppointmentListView.as_view(), name='appointment_list'),
    path('appointments/book/', engagement_api.AppointmentCreateView.as_view(), name='appointment_book'),

    # Daily inspiration (Home hero, design 19/22)
    path('inspiration/today/', engagement_api.InspirationTodayView.as_view(), name='inspiration_today'),

    # Practices (design 27)
    path('practices/', practices_api.PracticeListView.as_view(), name='practice_list'),
    path('practice/summary/', practices_api.PracticeSummaryView.as_view(), name='practice_summary'),
    path('practice/log/', practices_api.PracticeLogView.as_view(), name='practice_log'),

    # Upcoming Activities feed (design 25)
    path('activities/upcoming/', activities_api.UpcomingActivitiesView.as_view(), name='activities_upcoming'),
    path('activities/reminder/', activities_api.ReminderToggleView.as_view(), name='activities_reminder'),

    # Groups — browse + approval-gated join requests
    path('groups/', groups_api.GroupListView.as_view(), name='group_list'),
    path('groups/mine/', groups_api.MyGroupsView.as_view(), name='my_groups'),
    path('groups/<int:pk>/join/', groups_api.JoinRequestView.as_view(), name='group_join'),
]
