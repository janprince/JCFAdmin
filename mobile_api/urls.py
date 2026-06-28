"""Mobile app API — versioned namespace mounted at /api/mobile/v1/."""
from django.urls import path

from . import views
from . import content

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
]
