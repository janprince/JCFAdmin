from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from dashboard.listing import count_by, tabs
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
        cause_type = self.request.GET.get('type')
        if cause_type in ('specific', 'ongoing'):
            qs = qs.filter(type=cause_type)
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
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['categories'] = CauseCategory.objects.all()
        counts = count_by(Cause.objects.all(), 'is_active')
        context['tabs'] = tabs(self.request, 'status', [
            ('active', 'Active', counts.get(True, 0)),
            ('inactive', 'Inactive', counts.get(False, 0)),
        ], total=sum(counts.values()))
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
    template_name = 'confirm_delete.html'
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
            qs = qs.filter(Q(donor_name__icontains=q) | Q(donor_email__icontains=q) | Q(reference__icontains=q) | Q(paystack_reference__icontains=q))
        method = self.request.GET.get('method')
        if method:
            qs = qs.filter(method=method)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        cause = self.request.GET.get('cause')
        if cause == 'general':
            qs = qs.filter(cause__isnull=True)
        elif cause:
            qs = qs.filter(cause_id=cause) if cause.isdecimal() and len(cause) < 19 else qs.none()
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
        context['totals_by_currency'] = all_donations.filter(status='completed').order_by('currency').values('currency').annotate(total=Sum('amount'))
        context['pending_count'] = all_donations.filter(status='pending').count()
        context['completed_count'] = all_donations.filter(status='completed').count()
        counts = count_by(Donation.objects.all(), 'status')
        context['tabs'] = tabs(self.request, 'status', [
            (value, label, counts.get(value, 0)) for value, label in Donation.Status.choices
        ], total=sum(counts.values()))
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
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('causes:donation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Donation deleted.')
        return super().form_valid(form)
