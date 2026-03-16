from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from members.models import Contact
from .models import Consultation
from .forms import ConsultationForm


class ConsultationListView(LoginRequiredMixin, ListView):
    model = Consultation
    template_name = 'consultations/consultation_list.html'
    context_object_name = 'consultations'
    paginate_by = 50

    def get_queryset(self):
        qs = Consultation.objects.filter(done=False).select_related('contact').order_by('scheduled_date')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(contact__full_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class ConsultationCreateView(LoginRequiredMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/consultation_form.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def get_initial(self):
        initial = super().get_initial()
        contact_pk = self.request.GET.get('contact')
        if contact_pk:
            initial['contact'] = contact_pk
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact_pk = self.request.GET.get('contact')
        if contact_pk:
            context['selected_contact'] = get_object_or_404(Contact, pk=contact_pk)
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Consultation booked successfully.')
        return super().form_valid(form)


class ConsultationUpdateView(LoginRequiredMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/consultation_form.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Consultation updated successfully.')
        return super().form_valid(form)


@login_required
def mark_complete(request, pk):
    consultation = get_object_or_404(Consultation, pk=pk)
    consultation.done = True
    consultation.save()
    messages.success(request, f'Consultation #{pk} marked complete.')
    return redirect('consultations:consultation_list')


@login_required
def delete_consultation(request, pk):
    consultation = get_object_or_404(Consultation, pk=pk)
    name = consultation.contact.full_name
    consultation.delete()
    messages.success(request, f'Consultation with {name} deleted.')
    return redirect('consultations:consultation_list')
