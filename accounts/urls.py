from django.urls import path
from .views import OwnPasswordChangeView
app_name = 'accounts'
urlpatterns = [path('password/', OwnPasswordChangeView.as_view(), name='password_change')]
