import logging

from django.contrib import messages

logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .forms import (
    GalleryItemForm, VolunteerOpportunityForm, TestimonialForm,
    TeamMemberForm, ImpactStatForm,
)
from .models import (
    GalleryItem, VolunteerOpportunity, Testimonial, TeamMember,
    ImpactStat, ContactSubmission, VolunteerApplication,
    JoinCentreRequest, NewsletterSubscriber,
)


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

class GalleryListView(LoginRequiredMixin, ListView):
    model = GalleryItem
    template_name = 'website/gallery_list.html'
    context_object_name = 'items'
    paginate_by = 24

    def get_queryset(self):
        qs = GalleryItem.objects.all()
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = GalleryItem.CATEGORY_CHOICES
        context['active_category'] = self.request.GET.get('category', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class GalleryCreateView(LoginRequiredMixin, CreateView):
    model = GalleryItem
    form_class = GalleryItemForm
    template_name = 'website/gallery_form.html'
    success_url = reverse_lazy('website:gallery_list')

    def form_valid(self, form):
        messages.success(self.request, 'Gallery item added.')
        return super().form_valid(form)


class GalleryUpdateView(LoginRequiredMixin, UpdateView):
    model = GalleryItem
    form_class = GalleryItemForm
    template_name = 'website/gallery_form.html'
    success_url = reverse_lazy('website:gallery_list')

    def form_valid(self, form):
        messages.success(self.request, 'Gallery item updated.')
        return super().form_valid(form)


class GalleryDeleteView(LoginRequiredMixin, DeleteView):
    model = GalleryItem
    success_url = reverse_lazy('website:gallery_list')

    def form_valid(self, form):
        messages.success(self.request, 'Gallery item deleted.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Volunteer Opportunities
# ---------------------------------------------------------------------------

class VolunteerOpportunityListView(LoginRequiredMixin, ListView):
    model = VolunteerOpportunity
    template_name = 'website/volunteer_list.html'
    context_object_name = 'opportunities'
    paginate_by = 50

    def get_queryset(self):
        qs = VolunteerOpportunity.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['form'] = VolunteerOpportunityForm()
        return context


class VolunteerOpportunityCreateView(LoginRequiredMixin, CreateView):
    model = VolunteerOpportunity
    form_class = VolunteerOpportunityForm
    template_name = 'website/volunteer_list.html'
    success_url = reverse_lazy('website:volunteer_list')

    def form_valid(self, form):
        messages.success(self.request, 'Volunteer opportunity added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['opportunities'] = VolunteerOpportunity.objects.all()
        return self.render_to_response(context)


class VolunteerOpportunityUpdateView(LoginRequiredMixin, UpdateView):
    model = VolunteerOpportunity
    form_class = VolunteerOpportunityForm
    template_name = 'website/volunteer_form.html'
    success_url = reverse_lazy('website:volunteer_list')

    def form_valid(self, form):
        messages.success(self.request, 'Volunteer opportunity updated.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Testimonials
# ---------------------------------------------------------------------------

class TestimonialListView(LoginRequiredMixin, ListView):
    model = Testimonial
    template_name = 'website/testimonial_list.html'
    context_object_name = 'testimonials'
    paginate_by = 50

    def get_queryset(self):
        qs = Testimonial.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['form'] = TestimonialForm()
        return context


class TestimonialCreateView(LoginRequiredMixin, CreateView):
    model = Testimonial
    form_class = TestimonialForm
    template_name = 'website/testimonial_list.html'
    success_url = reverse_lazy('website:testimonial_list')

    def form_valid(self, form):
        messages.success(self.request, 'Testimonial added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['testimonials'] = Testimonial.objects.all()
        return self.render_to_response(context)


class TestimonialUpdateView(LoginRequiredMixin, UpdateView):
    model = Testimonial
    form_class = TestimonialForm
    template_name = 'website/testimonial_form.html'
    success_url = reverse_lazy('website:testimonial_list')

    def form_valid(self, form):
        messages.success(self.request, 'Testimonial updated.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Team Members
# ---------------------------------------------------------------------------

class TeamMemberListView(LoginRequiredMixin, ListView):
    model = TeamMember
    template_name = 'website/team_list.html'
    context_object_name = 'team_members'
    paginate_by = 50

    def get_queryset(self):
        qs = TeamMember.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['form'] = TeamMemberForm()
        return context


class TeamMemberCreateView(LoginRequiredMixin, CreateView):
    model = TeamMember
    form_class = TeamMemberForm
    template_name = 'website/team_list.html'
    success_url = reverse_lazy('website:team_list')

    def form_valid(self, form):
        messages.success(self.request, 'Team member added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['team_members'] = TeamMember.objects.all()
        return self.render_to_response(context)


class TeamMemberUpdateView(LoginRequiredMixin, UpdateView):
    model = TeamMember
    form_class = TeamMemberForm
    template_name = 'website/team_form.html'
    success_url = reverse_lazy('website:team_list')

    def form_valid(self, form):
        messages.success(self.request, 'Team member updated.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Impact Stats
# ---------------------------------------------------------------------------

class ImpactStatListView(LoginRequiredMixin, ListView):
    model = ImpactStat
    template_name = 'website/impact_list.html'
    context_object_name = 'stats'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ImpactStatForm()
        return context


class ImpactStatCreateView(LoginRequiredMixin, CreateView):
    model = ImpactStat
    form_class = ImpactStatForm
    template_name = 'website/impact_list.html'
    success_url = reverse_lazy('website:impact_list')

    def form_valid(self, form):
        messages.success(self.request, 'Impact stat added.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.warning(self.request, 'Please correct the errors below.')
        context = self.get_context_data(form=form)
        context['stats'] = ImpactStat.objects.all()
        return self.render_to_response(context)


class ImpactStatUpdateView(LoginRequiredMixin, UpdateView):
    model = ImpactStat
    form_class = ImpactStatForm
    template_name = 'website/impact_form.html'
    success_url = reverse_lazy('website:impact_list')

    def form_valid(self, form):
        messages.success(self.request, 'Impact stat updated.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Contact Submissions (read-only)
# ---------------------------------------------------------------------------

class ContactSubmissionListView(LoginRequiredMixin, ListView):
    model = ContactSubmission
    template_name = 'website/contact_list.html'
    context_object_name = 'submissions'
    paginate_by = 50

    def get_queryset(self):
        qs = ContactSubmission.objects.all()
        status = self.request.GET.get('status')
        if status == 'unread':
            qs = qs.filter(is_read=False)
        elif status == 'read':
            qs = qs.filter(is_read=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_status'] = self.request.GET.get('status', '')
        context['unread_count'] = ContactSubmission.objects.filter(is_read=False).count()
        return context


@login_required
def mark_contact_read(request, pk):
    submission = get_object_or_404(ContactSubmission, pk=pk)
    submission.is_read = True
    submission.save()
    messages.success(request, f'Marked "{submission.subject}" as read.')
    return redirect('website:contact_list')


# ---------------------------------------------------------------------------
# Volunteer Applications (with status update)
# ---------------------------------------------------------------------------

class VolunteerApplicationListView(LoginRequiredMixin, ListView):
    model = VolunteerApplication
    template_name = 'website/volunteer_app_list.html'
    context_object_name = 'applications'
    paginate_by = 50

    def get_queryset(self):
        qs = VolunteerApplication.objects.all()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_status'] = self.request.GET.get('status', '')
        context['status_choices'] = VolunteerApplication.Status.choices
        return context


@login_required
def update_volunteer_app_status(request, pk, status):
    application = get_object_or_404(VolunteerApplication, pk=pk)
    if status in dict(VolunteerApplication.Status.choices):
        application.status = status
        application.save()
        messages.success(request, f'Application from {application.name} marked as {application.get_status_display()}.')
    return redirect('website:volunteer_app_list')


# ---------------------------------------------------------------------------
# Join Centre Requests (with status update)
# ---------------------------------------------------------------------------

class JoinCentreRequestListView(LoginRequiredMixin, ListView):
    model = JoinCentreRequest
    template_name = 'website/join_requests_list.html'
    context_object_name = 'requests'
    paginate_by = 50

    def get_queryset(self):
        qs = JoinCentreRequest.objects.select_related('centre').all()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_status'] = self.request.GET.get('status', '')
        context['status_choices'] = JoinCentreRequest.Status.choices
        return context


@login_required
def update_join_request_status(request, pk, status):
    from members.models import Contact
    from .notifications import send_approval_notification

    join_request = get_object_or_404(JoinCentreRequest, pk=pk)
    if status not in dict(JoinCentreRequest.Status.choices):
        return redirect('website:join_request_list')

    join_request.status = status
    join_request.save()

    if status == 'approved' and join_request.centre:
        # Deduplicate by phone number
        contact = Contact.objects.filter(phone=join_request.phone).first()
        if contact:
            contact.centre = join_request.centre
            contact.is_member = True
            contact.is_active = True
            if join_request.email and not contact.email:
                contact.email = join_request.email
            contact.save()
        else:
            contact = Contact.objects.create(
                full_name=join_request.name,
                phone=join_request.phone,
                email=join_request.email,
                centre=join_request.centre,
                is_member=True,
                is_active=True,
            )

        try:
            send_approval_notification(join_request, contact)
        except Exception:
            logger.exception('Failed to send approval notification for %s', join_request.name)

    messages.success(request, f'Request from {join_request.name} marked as {join_request.get_status_display()}.')
    return redirect('website:join_request_list')


# ---------------------------------------------------------------------------
# Newsletter Subscribers
# ---------------------------------------------------------------------------

class NewsletterSubscriberListView(LoginRequiredMixin, ListView):
    model = NewsletterSubscriber
    template_name = 'website/newsletter_list.html'
    context_object_name = 'subscribers'
    paginate_by = 50

    def get_queryset(self):
        qs = NewsletterSubscriber.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(email__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['total_active'] = NewsletterSubscriber.objects.filter(is_active=True).count()
        return context
