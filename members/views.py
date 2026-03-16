from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView

from .forms import ContactForm
from .models import Contact, DataFile, Inquiry


class ContactListView(LoginRequiredMixin, ListView):
    model = Contact
    template_name = 'members/contact_list.html'
    context_object_name = 'contacts'
    paginate_by = 50

    def get_queryset(self):
        qs = Contact.objects.all().order_by('-id')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(full_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_type'] = 'contacts'
        context['search_query'] = self.request.GET.get('q', '')
        return context


class MemberListView(LoginRequiredMixin, ListView):
    model = Contact
    template_name = 'members/contact_list.html'
    context_object_name = 'contacts'
    paginate_by = 50

    def get_queryset(self):
        qs = Contact.objects.filter(is_member=True).order_by('-id')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(full_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_type'] = 'members'
        context['search_query'] = self.request.GET.get('q', '')
        return context


class StudentListView(LoginRequiredMixin, ListView):
    model = Contact
    template_name = 'members/contact_list.html'
    context_object_name = 'contacts'
    paginate_by = 50

    def get_queryset(self):
        qs = Contact.objects.filter(is_student=True).order_by('-id')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(full_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_type'] = 'students'
        context['search_query'] = self.request.GET.get('q', '')
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
