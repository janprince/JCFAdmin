from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import (EnrolmentForm, MentorshipForm, MilestoneForm,
                    PracticeAssignmentForm)
from .models import Enrolment, Mentorship, Milestone, PracticeAssignment


class StudiesListView(LoginRequiredMixin, ListView):
    """One dashboard page for the whole student domain."""

    model = Enrolment
    template_name = 'studies/studies_list.html'
    context_object_name = 'enrolments'

    def get_queryset(self):
        return Enrolment.objects.select_related(
            'contact', 'program', 'series')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['assignments'] = PracticeAssignment.objects.select_related(
            'contact', 'practice')[:50]
        ctx['milestones'] = Milestone.objects.select_related('program')
        ctx['mentorships'] = Mentorship.objects.select_related(
            'student', 'mentor__contact')
        return ctx


class _Create(LoginRequiredMixin, CreateView):
    template_name = 'studies/studies_form.html'
    success_url = reverse_lazy('studies:studies_list')

    def form_valid(self, form):
        messages.success(self.request, 'Saved.')
        return super().form_valid(form)


class _Update(LoginRequiredMixin, UpdateView):
    template_name = 'studies/studies_form.html'
    success_url = reverse_lazy('studies:studies_list')

    def form_valid(self, form):
        messages.success(self.request, 'Updated.')
        return super().form_valid(form)


class EnrolmentCreateView(_Create):
    model = Enrolment
    form_class = EnrolmentForm


class EnrolmentUpdateView(_Update):
    model = Enrolment
    form_class = EnrolmentForm


class AssignmentCreateView(_Create):
    model = PracticeAssignment
    form_class = PracticeAssignmentForm


class AssignmentUpdateView(_Update):
    model = PracticeAssignment
    form_class = PracticeAssignmentForm


class MilestoneCreateView(_Create):
    model = Milestone
    form_class = MilestoneForm


class MilestoneUpdateView(_Update):
    model = Milestone
    form_class = MilestoneForm


class MentorshipCreateView(_Create):
    model = Mentorship
    form_class = MentorshipForm


class MentorshipUpdateView(_Update):
    model = Mentorship
    form_class = MentorshipForm
