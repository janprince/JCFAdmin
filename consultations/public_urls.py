from django.urls import path
from . import public

app_name = 'booking'

urlpatterns = [
    path('', public.BookingFormView.as_view(), name='form'),
    path('thanks/', public.BookingThanksView.as_view(), name='thanks'),
]
