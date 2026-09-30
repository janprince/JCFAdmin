"""Mobile app API — versioned namespace mounted at /api/mobile/v1/."""
from django.urls import path

from . import views
from . import bootstrap_api
from . import content
from . import payments
from . import programs_api
from . import engagement_api
from . import groups_api
from . import practices_api
from . import activities_api
from . import continue_learning_api
from . import search_api
from . import member_home_api
from . import student_home_api
from . import inspiration_detail_api
from . import live_api

app_name = 'mobile_api'

urlpatterns = [
    # App bootstrap — version, maintenance and session, before anything else
    path('bootstrap/', bootstrap_api.BootstrapView.as_view(), name='bootstrap'),

    # Auth
    path('auth/request-code/', views.RequestCodeView.as_view(), name='request_code'),
    path('auth/verify-code/', views.VerifyCodeView.as_view(), name='verify_code'),
    path('auth/refresh/', views.RefreshView.as_view(), name='refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),

    # Content — teachings (lessons) + series
    path('teachings/', content.TeachingListView.as_view(), name='teaching_list'),
    path('teachings/<slug:slug>/', content.TeachingDetailView.as_view(), name='teaching_detail'),
    path('teachings/<slug:slug>/progress/', content.TeachingProgressView.as_view(), name='teaching_progress'),
    # The compact series + recently-viewed summary the home card reads.
    # The full hub lives at learning/continue/ below.
    path('learning/summary/', content.ContinueLearningView.as_view(), name='continue_learning'),
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
    path('announcements/<int:pk>/read/', engagement_api.AnnouncementReadView.as_view(), name='announcement_read'),
    path('devices/register/', engagement_api.DeviceRegisterView.as_view(), name='device_register'),
    path('devices/<str:token>/', engagement_api.DeviceUnregisterView.as_view(), name='device_unregister'),
    path('notifications/', engagement_api.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/read/', engagement_api.NotificationReadView.as_view(), name='notification_read'),
    path('appointments/', engagement_api.AppointmentListView.as_view(), name='appointment_list'),
    path('appointments/book/', engagement_api.AppointmentCreateView.as_view(), name='appointment_book'),

    # Daily inspiration (Home hero, design 19/22)
    path('inspiration/today/', engagement_api.InspirationTodayView.as_view(), name='inspiration_today'),
    path('inspiration/recent/', engagement_api.InspirationRecentView.as_view(), name='inspiration_recent'),
    path('inspirations/<str:identifier>/', inspiration_detail_api.InspirationDetailView.as_view(), name='inspiration_detail'),
    path('inspirations/<str:identifier>/share-data/', inspiration_detail_api.InspirationShareDataView.as_view(), name='inspiration_share_data'),
    path('inspirations/<str:identifier>/save/', inspiration_detail_api.InspirationSaveView.as_view(), name='inspiration_save'),
    path('inspirations/<str:identifier>/reflection/', inspiration_detail_api.InspirationReflectionView.as_view(), name='inspiration_reflection'),

    # Practices (design 27)
    path('practices/', practices_api.PracticeListView.as_view(), name='practice_list'),
    path('practice/summary/', practices_api.PracticeSummaryView.as_view(), name='practice_summary'),
    path('practice/log/', practices_api.PracticeLogView.as_view(), name='practice_log'),

    # Upcoming Activities feed (design 25)
    path('activities/upcoming/', activities_api.UpcomingActivitiesView.as_view(), name='activities_upcoming'),
    path('activities/calendar/', activities_api.ActivityCalendarView.as_view(), name='activities_calendar'),
    path('activities/reminder/', activities_api.ReminderToggleView.as_view(), name='activities_reminder'),
    path('activities/save/', activities_api.ActivitySaveToggleView.as_view(), name='activities_save'),
    path('activities/register/', activities_api.ActivityRegistrationView.as_view(), name='activities_register'),
    path('activities/<int:pk>/', activities_api.ActivityDetailView.as_view(), name='activities_detail'),

    # Continue Learning hub (designs 43-47)
    path('learning/continue/', continue_learning_api.ContinueLearningView.as_view(), name='learning_continue'),
    path('learning/lessons/<int:pk>/progress/', continue_learning_api.LessonProgressView.as_view(), name='learning_lesson_progress'),

    # Member Home aggregate
    path('home/member/', member_home_api.MemberHomeView.as_view(), name='member_home'),

    path('home/student/', student_home_api.StudentHomeView.as_view(), name='student_home'),

    # Live Now (design 24)
    path('events/<int:event_id>/live/', live_api.LiveEventDetailView.as_view(), name='live_detail'),
    path('events/<int:event_id>/viewer-session/', live_api.LiveViewerSessionView.as_view(), name='live_viewer_session'),
    path('events/<int:event_id>/chat/', live_api.LiveChatView.as_view(), name='live_chat'),
    path('events/<int:event_id>/chat/<int:message_id>/report/', live_api.LiveChatReportView.as_view(), name='live_chat_report'),
    path('events/<int:event_id>/chat/block/<int:contact_id>/', live_api.LiveChatBlockView.as_view(), name='live_chat_block'),
    path('events/<int:event_id>/reaction/', live_api.LiveReactionView.as_view(), name='live_reaction'),
    path('events/<int:event_id>/save/', live_api.LiveSaveView.as_view(), name='live_save'),

    # Global search (designs 30/31)
    path('search/', search_api.GlobalSearchView.as_view(), name='search'),
    path('search/popular/', search_api.PopularSearchesView.as_view(), name='search_popular'),

    # Groups — browse + approval-gated join requests
    path('groups/', groups_api.GroupListView.as_view(), name='group_list'),
    path('groups/mine/', groups_api.MyGroupsView.as_view(), name='my_groups'),
    path('groups/<int:pk>/join/', groups_api.JoinRequestView.as_view(), name='group_join'),
]
