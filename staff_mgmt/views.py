from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from .forms import WorkerForm
from .models import Worker


class StaffListView(LoginRequiredMixin, ListView):
    model = Worker
    template_name = 'staff/staff_list.html'
    context_object_name = 'staff'
    paginate_by = 50

    def get_queryset(self):
        qs = Worker.objects.select_related('contact').order_by('-id')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(contact__full_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class StaffCreateView(LoginRequiredMixin, CreateView):
    model = Worker
    form_class = WorkerForm
    template_name = 'staff/staff_form.html'
    success_url = reverse_lazy('staff:staff_list')

    def form_valid(self, form):
        messages.success(self.request, 'Staff member added.')
        return super().form_valid(form)


class StaffUpdateView(LoginRequiredMixin, UpdateView):
    model = Worker
    form_class = WorkerForm
    template_name = 'staff/staff_form.html'
    success_url = reverse_lazy('staff:staff_list')

    def form_valid(self, form):
        messages.success(self.request, 'Staff member updated.')
        return super().form_valid(form)
