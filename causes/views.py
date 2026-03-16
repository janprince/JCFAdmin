from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .forms import CauseForm, DonationForm
from .models import Cause, Donation, CauseCategory


# ---------------------------------------------------------------------------
# Cause views
# ---------------------------------------------------------------------------

class CauseListView(LoginRequiredMixin, ListView):
    model = Cause
    template_name = 'causes/cause_list.html'
    context_object_name = 'causes'
    paginate_by = 20

    def get_queryset(self):
        qs = Cause.objects.select_related('category').order_by('-id')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(title__icontains=q)
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)
        status = self.request.GET.get('status')
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['categories'] = CauseCategory.objects.all()
        return context


class CauseCreateView(LoginRequiredMixin, CreateView):
    model = Cause
    form_class = CauseForm
    template_name = 'causes/cause_form.html'
    success_url = reverse_lazy('causes:cause_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cause created successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class CauseUpdateView(LoginRequiredMixin, UpdateView):
    model = Cause
    form_class = CauseForm
    template_name = 'causes/cause_form.html'
    success_url = reverse_lazy('causes:cause_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cause updated successfully.')
        return super().form_valid(form)


class CauseDetailView(LoginRequiredMixin, DetailView):
    model = Cause
    template_name = 'causes/cause_detail.html'
    context_object_name = 'cause'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['donations'] = self.object.donations.all().order_by('-donated_at')
        return context


class CauseDeleteView(LoginRequiredMixin, DeleteView):
    model = Cause
    success_url = reverse_lazy('causes:cause_list')

    def form_valid(self, form):
        messages.success(self.request, f'Cause "{self.object.title}" deleted.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Donation views
# ---------------------------------------------------------------------------

class DonationListView(LoginRequiredMixin, ListView):
    model = Donation
    template_name = 'causes/donation_list.html'
    context_object_name = 'donations'
    paginate_by = 50

    def get_queryset(self):
        qs = Donation.objects.select_related('cause').order_by('-donated_at')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(donor_name__icontains=q)
        method = self.request.GET.get('method')
        if method:
            qs = qs.filter(method=method)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        cause = self.request.GET.get('cause')
        if cause:
            qs = qs.filter(cause_id=cause)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_method'] = self.request.GET.get('method', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_cause'] = self.request.GET.get('cause', '')
        context['causes'] = Cause.objects.all()
        context['method_choices'] = Donation.Method.choices
        context['status_choices'] = Donation.Status.choices

        # Summary stats
        all_donations = Donation.objects.all()
        context['total_donations'] = all_donations.count()
        context['total_amount'] = all_donations.filter(status='completed').aggregate(
            total=Sum('amount'))['total'] or 0
        context['pending_count'] = all_donations.filter(status='pending').count()
        context['completed_count'] = all_donations.filter(status='completed').count()
        return context


class DonationCreateView(LoginRequiredMixin, CreateView):
    model = Donation
    form_class = DonationForm
    template_name = 'causes/donation_form.html'
    success_url = reverse_lazy('causes:donation_list')

    def get_initial(self):
        initial = super().get_initial()
        cause_id = self.request.GET.get('cause')
        if cause_id:
            initial['cause'] = cause_id
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Donation recorded successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class DonationUpdateView(LoginRequiredMixin, UpdateView):
    model = Donation
    form_class = DonationForm
    template_name = 'causes/donation_form.html'
    success_url = reverse_lazy('causes:donation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Donation updated successfully.')
        return super().form_valid(form)


class DonationDeleteView(LoginRequiredMixin, DeleteView):
    model = Donation
    success_url = reverse_lazy('causes:donation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Donation deleted.')
        return super().form_valid(form)
