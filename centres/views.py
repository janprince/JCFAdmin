from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .forms import CentreForm
from .models import Centre


class CentreListView(LoginRequiredMixin, ListView):
    model = Centre
    template_name = 'centres/centre_list.html'
    context_object_name = 'centres'
    paginate_by = 20

    def get_queryset(self):
        qs = Centre.objects.all().order_by('name')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(location__icontains=q)
                | Q(country__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class CentreCreateView(LoginRequiredMixin, CreateView):
    model = Centre
    form_class = CentreForm
    template_name = 'centres/centre_form.html'
    success_url = reverse_lazy('centres:centre_list')

    def form_valid(self, form):
        messages.success(self.request, 'Centre added successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class CentreUpdateView(LoginRequiredMixin, UpdateView):
    model = Centre
    form_class = CentreForm
    template_name = 'centres/centre_form.html'
    success_url = reverse_lazy('centres:centre_list')

    def form_valid(self, form):
        messages.success(self.request, 'Centre updated successfully.')
        return super().form_valid(form)


class CentreDeleteView(LoginRequiredMixin, DeleteView):
    model = Centre
    success_url = reverse_lazy('centres:centre_list')

    def form_valid(self, form):
        messages.success(self.request, f'{self.object.name} deleted.')
        return super().form_valid(form)
