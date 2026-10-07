"""The public booking form at /book/. No sign-in; see booking.py for what it may write."""
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.views.generic import FormView, TemplateView

from .booking import BookingThrottle, submit_request
from .forms import BookingRequestForm


def booking_link(request):
    """The address staff share. Production sits behind TLS-terminating proxies."""
    url = request.build_absolute_uri(reverse('booking:form'))
    return url if settings.DEBUG else url.replace('http://', 'https://', 1)


@method_decorator(never_cache, name='dispatch')
class BookingFormView(FormView):
    template_name = 'booking/form.html'
    form_class = BookingRequestForm

    def form_valid(self, form):
        if form.cleaned_data.get('website'):
            return redirect('booking:thanks')  # A bot: say thanks, keep nothing.
        if not BookingThrottle().allow_request(self.request, self):
            form.add_error(None, 'We have received several forms from this connection. Please try again in a while, or call the Foundation office.')
            return self.form_invalid(form)
        booking = submit_request(form.cleaned_data)
        self.request.session['booking_thanks'] = {'name': booking.full_name.split()[0], 'phone': booking.phone.as_international if booking.phone else ''}
        return redirect('booking:thanks')


@method_decorator(never_cache, name='dispatch')
class BookingThanksView(TemplateView):
    template_name = 'booking/thanks.html'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'sent': self.request.session.get('booking_thanks')}
