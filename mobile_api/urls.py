"""Mobile app API — versioned namespace mounted at /api/mobile/v1/."""
from django.urls import path

from . import views

app_name = 'mobile_api'

urlpatterns = [
    path('auth/request-code/', views.RequestCodeView.as_view(), name='request_code'),
    path('auth/verify-code/', views.VerifyCodeView.as_view(), name='verify_code'),
    path('auth/refresh/', views.RefreshView.as_view(), name='refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),
]
