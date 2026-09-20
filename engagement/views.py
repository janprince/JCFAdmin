from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, ListView, UpdateView

from .forms import AnnouncementForm, DailyInspirationForm, NotificationComposeForm
from .models import Announcement, DailyInspiration, Notification


class AnnouncementListView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = 'engagement/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 50


class AnnouncementCreateView(LoginRequiredMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'engagement/announcement_form.html'
    success_url = reverse_lazy('engagement:announcement_list')

    def form_valid(self, form):
        messages.success(self.request, 'Announcement published to the app.'
                         if form.instance.is_published else 'Announcement saved as draft.')
        return super().form_valid(form)


class AnnouncementUpdateView(LoginRequiredMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'engagement/announcement_form.html'
    success_url = reverse_lazy('engagement:announcement_list')

    def form_valid(self, form):
        messages.success(self.request, 'Announcement updated.')
        return super().form_valid(form)


@login_required
@require_POST
def announcement_delete(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    announcement.delete()
    messages.success(request, 'Announcement deleted.')
    return redirect('engagement:announcement_list')


@login_required
@require_POST
def announcement_toggle_pin(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    announcement.pinned = not announcement.pinned
    announcement.save(update_fields=['pinned'])
    messages.success(
        request,
        'Announcement pinned.' if announcement.pinned else 'Announcement unpinned.',
    )
    return redirect('engagement:announcement_list')


class NotificationComposeView(LoginRequiredMixin, FormView):
    """Send an in-app notification straight to members' mobile inboxes."""

    form_class = NotificationComposeForm
    template_name = 'engagement/notification_compose.html'
    success_url = reverse_lazy('engagement:notification_compose')

    def form_valid(self, form):
        recipients = form.recipients()
        Notification.objects.bulk_create([
            Notification(
                contact=contact,
                title=form.cleaned_data['title'],
                body=form.cleaned_data.get('body', ''),
            )
            for contact in recipients
        ])
        messages.success(
            self.request,
            f'Notification sent to {len(recipients)} '
            f'member{"s" if len(recipients) != 1 else ""}.',
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent'] = (
            Notification.objects.select_related('contact').order_by('-created_at')[:15]
        )
        return context


class InspirationListView(LoginRequiredMixin, ListView):
    model = DailyInspiration
    template_name = 'engagement/inspiration_list.html'
    context_object_name = 'inspirations'
    paginate_by = 50


class InspirationCreateView(LoginRequiredMixin, CreateView):
    model = DailyInspiration
    form_class = DailyInspirationForm
    template_name = 'engagement/inspiration_form.html'
    success_url = reverse_lazy('engagement:inspiration_list')

    def form_valid(self, form):
        messages.success(self.request, 'Daily inspiration scheduled.')
        return super().form_valid(form)


class InspirationUpdateView(LoginRequiredMixin, UpdateView):
    model = DailyInspiration
    form_class = DailyInspirationForm
    template_name = 'engagement/inspiration_form.html'
    success_url = reverse_lazy('engagement:inspiration_list')

    def form_valid(self, form):
        messages.success(self.request, 'Daily inspiration updated.')
        return super().form_valid(form)


@login_required
@require_POST
def inspiration_delete(request, pk):
    get_object_or_404(DailyInspiration, pk=pk).delete()
    messages.success(request, 'Daily inspiration deleted.')
    return redirect('engagement:inspiration_list')
