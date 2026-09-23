from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from centres.models import Centre
from dashboard.listing import count_by, tabs
from .forms import ContactForm
from .models import Contact, DataFile, Inquiry


def search_contacts(qs, q):
    """Match a name, an email, or a phone number typed the local way.

    Phones are stored as E.164 (+233542549699) but typed locally
    (054 254 9699), so digits are matched without a leading zero.
    """
    q = q.strip()
    if not q:
        return qs
    match = Q(full_name__icontains=q) | Q(email__icontains=q)
    digits = ''.join(c for c in q if c.isdigit()).lstrip('0')
    if len(digits) >= 4:
        match |= Q(phone__icontains=digits)
    return qs.filter(match)


class ContactFilterMixin:
    """Search, status and centre filters shared by the three contact lists."""
    base_filter = {}

    def get_queryset(self):
        qs = Contact.objects.filter(**self.base_filter).select_related('centre').order_by('-id')
        qs = search_contacts(qs, self.request.GET.get('q', ''))
        status = self.request.GET.get('status')
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        centre = self.request.GET.get('centre')
        if centre:
            qs = qs.filter(centre_id=centre)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['centre_filter'] = self.request.GET.get('centre', '')
        context['centres'] = Centre.objects.filter(is_active=True).order_by('name')
        return context

    def status_tabs(self):
        counts = count_by(Contact.objects.filter(**self.base_filter), 'is_active')
        return tabs(self.request, 'status', [
            ('active', 'Active', counts.get(True, 0)),
            ('inactive', 'Inactive', counts.get(False, 0)),
        ], total=sum(counts.values()))


class ContactListView(LoginRequiredMixin, ContactFilterMixin, ListView):
    model = Contact
    template_name = 'members/contact_list.html'
    context_object_name = 'contacts'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.GET.get('role')
        if role == 'member':
            qs = qs.filter(is_member=True)
        elif role == 'student':
            qs = qs.filter(is_student=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = count_by(Contact.objects.all(), 'is_active')
        context['active_count'] = counts.get(True, 0)
        context['inactive_count'] = counts.get(False, 0)
        context['tabs'] = tabs(self.request, 'role', [
            ('member', 'Members', Contact.objects.filter(is_member=True).count()),
            ('student', 'Students', Contact.objects.filter(is_student=True).count()),
        ], total=sum(counts.values()))
        return context


class MemberListView(LoginRequiredMixin, ContactFilterMixin, ListView):
    model = Contact
    template_name = 'members/member_list.html'
    context_object_name = 'contacts'
    paginate_by = 50
    base_filter = {'is_member': True}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tabs'] = self.status_tabs()
        return context


class StudentListView(LoginRequiredMixin, ContactFilterMixin, ListView):
    model = Contact
    template_name = 'members/student_list.html'
    context_object_name = 'contacts'
    paginate_by = 50
    base_filter = {'is_student': True}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tabs'] = self.status_tabs()
        return context


class ContactCreateView(LoginRequiredMixin, CreateView):
    model = Contact
    form_class = ContactForm
    template_name = 'members/contact_form.html'

    def get_success_url(self):
        return reverse_lazy('members:contact_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        self._save_datafiles(self.object)
        messages.success(self.request, 'Contact added successfully.')
        return response

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

    def _save_datafiles(self, contact):
        files = self.request.FILES.getlist('datafiles')
        for f in files:
            DataFile.objects.create(contact=contact, file=f)


class ContactUpdateView(LoginRequiredMixin, UpdateView):
    model = Contact
    form_class = ContactForm
    template_name = 'members/contact_form.html'

    def get_success_url(self):
        return reverse_lazy('members:contact_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        files = self.request.FILES.getlist('datafiles')
        for f in files:
            DataFile.objects.create(contact=self.object, file=f)
        messages.success(self.request, 'Record updated successfully.')
        return response


class ContactDetailView(LoginRequiredMixin, DetailView):
    model = Contact
    template_name = 'members/contact_detail.html'
    context_object_name = 'contact'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self.object
        context['inquiries'] = contact.inquiries.all()
        context['datafiles'] = contact.datafiles.all()
        try:
            context['pending_consultation'] = contact.consultations.get(done=False)
        except Exception:
            context['pending_consultation'] = None
        return context


class ContactDeleteView(LoginRequiredMixin, DeleteView):
    model = Contact
    success_url = reverse_lazy('members:contact_list')

    def form_valid(self, form):
        messages.success(self.request, f'{self.object.full_name} deleted.')
        return super().form_valid(form)


@login_required
def add_datafiles(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    if request.method == 'POST':
        files = request.FILES.getlist('datafiles')
        for f in files:
            DataFile.objects.create(contact=contact, file=f)
        messages.success(request, 'Files uploaded successfully.')
    return redirect('members:contact_detail', pk=pk)


@login_required
def delete_datafile(request, pk):
    datafile = get_object_or_404(DataFile, pk=pk)
    contact_pk = datafile.contact.pk
    datafile.delete()
    messages.success(request, 'File deleted.')
    return redirect('members:contact_detail', pk=contact_pk)


@login_required
def add_inquiry(request, contact_pk):
    contact = get_object_or_404(Contact, pk=contact_pk)
    if request.method == 'POST':
        Inquiry.objects.create(
            contact=contact,
            subject=request.POST.get('subject', ''),
            remark=request.POST.get('remark', ''),
            guidance=request.POST.get('guidance', ''),
        )
        messages.success(request, 'Inquiry added successfully.')
    return redirect('members:contact_detail', pk=contact_pk)


@login_required
def update_inquiry(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    contact_id = request.GET.get('contact_id', inquiry.contact.pk)
    if request.method == 'POST':
        inquiry.subject = request.POST.get('subject', '')
        inquiry.remark = request.POST.get('remark', '')
        inquiry.guidance = request.POST.get('guidance', '')
        inquiry.save()
        messages.success(request, 'Inquiry updated successfully.')
    return redirect('members:contact_detail', pk=contact_id)


@login_required
def delete_inquiry(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    contact_id = request.GET.get('contact_id', inquiry.contact.pk)
    inquiry.delete()
    messages.success(request, 'Inquiry deleted.')
    return redirect('members:contact_detail', pk=contact_id)
