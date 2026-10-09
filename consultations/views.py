from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView

from members.models import Contact
from dashboard.listing import count_by, tabs
from .models import Consultation, ConsultationRequest
from .forms import ConsultationForm
from .public import booking_link
from .sms import text_booking


def notify_by_sms(request, consultation, rescheduled=False):
    """Text the date. Call only after the booking is committed: a failure is a warning, never an error."""
    sent, note = text_booking(consultation, rescheduled=rescheduled)
    (messages.info if sent else messages.warning)(request, note)


def share_context(request):
    url = booking_link(request)
    return {'booking_url': url,
            'booking_message': f'Hello! To book your consultation with Dr. Baffour Jan, please fill in your details here — it takes about two minutes: {url}'}


class ConsultationListView(LoginRequiredMixin, ListView):
    model = Consultation
    template_name = 'consultations/consultation_list.html'
    context_object_name = 'consultations'
    paginate_by = 50

    def get_queryset(self):
        selected = self.request.GET.get('show', '')
        done = selected == 'done'
        # Upcoming: soonest first. Completed: most recent first.
        qs = (Consultation.objects.filter(done=done).select_related('contact')
              .order_by('-scheduled_date' if done else 'scheduled_date'))
        if selected == 'today':
            qs = qs.filter(scheduled_date=timezone.localdate())
        elif selected == 'overdue':
            qs = qs.filter(scheduled_date__lt=timezone.localdate())
        elif not done:
            qs = qs.filter(scheduled_date__gte=timezone.localdate())
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(contact__full_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['showing_done'] = self.request.GET.get('show') == 'done'
        counts = count_by(Consultation.objects.all(), 'done')
        context['tabs'] = tabs(self.request, 'show', [
            ('', 'Upcoming', Consultation.objects.filter(done=False, scheduled_date__gte=timezone.localdate()).count()),
            ('today', 'Today', Consultation.objects.filter(done=False, scheduled_date=timezone.localdate()).count()),
            ('overdue', 'Needs an update', Consultation.objects.filter(done=False, scheduled_date__lt=timezone.localdate()).count()),
            ('done', 'Completed', counts.get(True, 0)),
        ], all_label=None)
        context.update(share_context(self.request),
                       new_request_count=ConsultationRequest.objects.filter(status=ConsultationRequest.Status.NEW).count())
        return context


class ConsultationCreateView(LoginRequiredMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/consultation_form.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def booking_request(self):
        """The open request this booking answers, from ?request= on the URL."""
        pk = self.request.GET.get('request', '')
        if not pk.isdigit():
            return None
        return ConsultationRequest.objects.filter(pk=pk, status=ConsultationRequest.Status.NEW, contact__isnull=False).first()

    def get_initial(self):
        initial = super().get_initial()
        contact_pk = self.request.GET.get('contact')
        if contact_pk:
            initial['contact'] = contact_pk
        booking = self.booking_request()
        if booking:
            initial['contact'] = booking.contact_id
            if booking.preferred_mode:
                initial['mode'] = booking.preferred_mode
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = self.booking_request()
        contact_pk = booking.contact_id if booking else self.request.GET.get('contact')
        if contact_pk:
            context['selected_contact'] = get_object_or_404(Contact, pk=contact_pk)
        context['booking_request'] = booking
        return context

    def form_valid(self, form):
        # Save the booking (and close its request) first; the SMS goes out after.
        with transaction.atomic():
            response = super().form_valid(form)
            booking = self.booking_request()
            if booking and booking.contact_id == self.object.contact_id:
                booking.status = ConsultationRequest.Status.BOOKED
                booking.consultation = self.object
                booking.handled_by, booking.handled_at = self.request.user, timezone.now()
                booking.save(update_fields=['status', 'consultation', 'handled_by', 'handled_at'])
                messages.success(self.request, f'Consultation booked for {self.object.contact.full_name}. Their booking request is marked booked.')
            else:
                messages.success(self.request, 'Consultation booked successfully.')
        if form.cleaned_data.get('send_sms'):
            notify_by_sms(self.request, self.object)
        return response


class ConsultationUpdateView(LoginRequiredMixin, UpdateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/consultation_form.html'
    success_url = reverse_lazy('consultations:consultation_list')

    def form_valid(self, form):
        rescheduled = 'scheduled_date' in form.changed_data
        response = super().form_valid(form)
        messages.success(self.request, 'Consultation updated successfully.')
        if form.cleaned_data.get('send_sms'):
            notify_by_sms(self.request, self.object, rescheduled=rescheduled)
        return response


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


class RequestListView(LoginRequiredMixin, ListView):
    """Booking requests from the public form. Opens on the ones waiting for a date."""
    template_name = 'consultations/request_list.html'
    context_object_name = 'requests'
    paginate_by = 50

    def get_queryset(self):
        qs = ConsultationRequest.objects.select_related('contact', 'consultation')
        status = self.request.GET.get('status', 'new')
        if status in ConsultationRequest.Status.values:
            qs = qs.filter(status=status)
        query = self.request.GET.get('q', '').strip()
        if query:
            digits = ''.join(c for c in query if c.isdigit()).lstrip('0')
            match = Q(full_name__icontains=query) | Q(residence__icontains=query)
            if len(digits) >= 4:
                match |= Q(phone__icontains=digits)
            qs = qs.filter(match)
        # Oldest waiting first, so nobody is left at the bottom of the list.
        return qs.order_by('created_at') if status == 'new' else qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = count_by(ConsultationRequest.objects.all(), 'status')
        context['tabs'] = tabs(self.request, 'status', [
            ('new', 'Waiting', counts.get('new', 0)),
            ('booked', 'Booked', counts.get('booked', 0)),
            ('closed', 'Closed', counts.get('closed', 0)),
            ('all', 'All', sum(counts.values())),
        ], all_label=None, default='new')
        context['search_query'] = self.request.GET.get('q', '')
        context.update(share_context(self.request))
        return context


class RequestDetailView(LoginRequiredMixin, DetailView):
    template_name = 'consultations/request_detail.html'
    context_object_name = 'booking'

    def get_queryset(self):
        return ConsultationRequest.objects.select_related('contact', 'consultation', 'handled_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = self.object
        context['shares_phone'] = (Contact.objects.filter(phone=booking.phone).exclude(pk=booking.contact_id)
                                   .order_by('full_name')[:5]) if booking.phone else []
        context['removable'] = self.removable(booking)
        return context

    @staticmethod
    def removable(booking):
        """Spam removal also deletes the contact, but only one this form created and nobody has used since."""
        contact = booking.contact
        return bool(booking.created_contact and contact and booking.status == ConsultationRequest.Status.NEW
                    and not contact.consultations.exists() and not contact.inquiries.exists()
                    and not contact.datafiles.exists() and contact.booking_requests.count() == 1
                    and not hasattr(contact, 'worker'))


class RequestActionView(LoginRequiredMixin, View):
    """Close, reopen or remove a request. POST only."""
    def post(self, request, pk, action):
        booking = get_object_or_404(ConsultationRequest.objects.select_related('contact'), pk=pk)
        if action == 'close' and booking.status == ConsultationRequest.Status.NEW:
            booking.status = ConsultationRequest.Status.CLOSED
            booking.handled_by, booking.handled_at = request.user, timezone.now()
            booking.save(update_fields=['status', 'handled_by', 'handled_at'])
            messages.success(request, f'Request from {booking.full_name} closed. Their contact record stays.')
        elif action == 'reopen' and booking.status == ConsultationRequest.Status.CLOSED:
            booking.status = ConsultationRequest.Status.NEW
            booking.handled_by = booking.handled_at = None
            booking.save(update_fields=['status', 'handled_by', 'handled_at'])
            messages.success(request, f'Request from {booking.full_name} is waiting again.')
        elif action == 'spam' and RequestDetailView.removable(booking):
            with transaction.atomic():
                name = booking.full_name
                contact = booking.contact
                booking.delete()
                contact.delete()
            messages.success(request, f'Removed the request from “{name}” and the contact it created.')
            return redirect('consultations:request_list')
        else:
            messages.warning(request, 'That request has already been handled.')
        return redirect('consultations:request_detail', pk=pk)
