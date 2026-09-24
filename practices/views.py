from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import PracticeForm
from .models import Practice


class PracticeListView(LoginRequiredMixin, ListView):
    model = Practice
    template_name = 'practices/practice_list.html'
    context_object_name = 'practices'
    paginate_by = 50


class PracticeCreateView(LoginRequiredMixin, CreateView):
    model = Practice
    form_class = PracticeForm
    template_name = 'practices/practice_form.html'
    success_url = reverse_lazy('practices:practice_list')

    def form_valid(self, form):
        messages.success(self.request, 'Practice created.')
        return super().form_valid(form)


class PracticeUpdateView(LoginRequiredMixin, UpdateView):
    model = Practice
    form_class = PracticeForm
    template_name = 'practices/practice_form.html'
    success_url = reverse_lazy('practices:practice_list')

    def form_valid(self, form):
        messages.success(self.request, 'Practice updated.')
        return super().form_valid(form)
