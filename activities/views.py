from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import ActivityForm
from .models import Activity


class ActivityListView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'activities/activity_list.html'
    context_object_name = 'activities'
    paginate_by = 50

    def get_queryset(self):
        return Activity.objects.order_by('-starts_at')


class ActivityCreateView(LoginRequiredMixin, CreateView):
    model = Activity
    form_class = ActivityForm
    template_name = 'activities/activity_form.html'
    success_url = reverse_lazy('activities:activity_list')

    def form_valid(self, form):
        messages.success(self.request, 'Activity scheduled.')
        return super().form_valid(form)


class ActivityUpdateView(LoginRequiredMixin, UpdateView):
    model = Activity
    form_class = ActivityForm
    template_name = 'activities/activity_form.html'
    success_url = reverse_lazy('activities:activity_list')

    def form_valid(self, form):
        messages.success(self.request, 'Activity updated.')
        return super().form_valid(form)
