from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from .forms import TeachingForm
from .models import Teaching


class TeachingListView(LoginRequiredMixin, ListView):
    model = Teaching
    template_name = 'teachings/teaching_list.html'
    context_object_name = 'teachings'
    paginate_by = 50

    def get_queryset(self):
        qs = Teaching.objects.all().order_by('-id')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(topic__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['form'] = TeachingForm()
        return context


class TeachingCreateView(LoginRequiredMixin, CreateView):
    model = Teaching
    form_class = TeachingForm
    template_name = 'teachings/teaching_list.html'
    success_url = reverse_lazy('teachings:teaching_list')

    def form_valid(self, form):
        messages.success(self.request, 'Teaching added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['teachings'] = Teaching.objects.all().order_by('-id')
        return self.render_to_response(context)


class TeachingUpdateView(LoginRequiredMixin, UpdateView):
    model = Teaching
    form_class = TeachingForm
    template_name = 'teachings/teaching_form.html'
    success_url = reverse_lazy('teachings:teaching_list')

    def form_valid(self, form):
        messages.success(self.request, 'Teaching updated.')
        return super().form_valid(form)
