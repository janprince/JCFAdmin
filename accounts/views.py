from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache

from .forms import OwnPasswordForm
from .models import PortalAccessEvent


@method_decorator(sensitive_post_parameters(), name='dispatch')
@method_decorator(never_cache, name='dispatch')
class OwnPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = OwnPasswordForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('dashboard:analytics')

    def form_valid(self, form):
        with transaction.atomic():
            form.user.must_change_password = False
            form.save()
            PortalAccessEvent.objects.create(actor=self.request.user, target=self.request.user,
                                            action='Password changed')
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, 'Your password has been changed. Welcome to the Foundation office.')
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())
