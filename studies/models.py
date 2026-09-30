"""
The student domain: what a JCF student is enrolled in, what they have been
assigned, the milestones they are working toward and who mentors them.

Members browse; students are *enrolled*. Everything here is authored by
staff in the dashboard — the app never invents an enrolment, an assignment
or a milestone.
"""
from datetime import timedelta

from django.db import models
from django.utils import timezone


class Enrolment(models.Model):
    """A student's place on a programme, and the curriculum it follows."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        EXPIRED = 'expired', 'Access expired'
        SUSPENDED = 'suspended', 'Suspended'

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE, related_name='enrolments')
    program = models.ForeignKey(
        'programs.Program', on_delete=models.CASCADE,
        related_name='enrolments')
    # The curriculum the student works through. Progress is computed from
    # this series' published lessons, never stored as a stale number.
    series = models.ForeignKey(
        'teachings.TeachingSeries', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='enrolments')

    cohort = models.CharField(
        max_length=120, blank=True,
        help_text='e.g. "Cohort 3" or "January intake".')
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE)
    is_primary = models.BooleanField(
        default=False,
        help_text='Shown in the app hero when a student has several.')
    access_expires_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-last_accessed_at', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'program'], name='uniq_enrolment'),
        ]

    @property
    def is_open(self):
        """Only an active, unexpired enrolment may be continued."""
        if self.status != self.Status.ACTIVE:
            return False
        expires = self.access_expires_at
        return expires is None or expires > timezone.now()

    def lessons(self):
        from teachings.models import Teaching
        if self.series_id is None:
            return []
        return list(
            self.series.teachings.filter(status=Teaching.Status.PUBLISHED)
            .order_by('order', 'id'))

    def __str__(self):
        return f'{self.contact.full_name} — {self.program.title}'


class PracticeAssignment(models.Model):
    """A practice a student has been asked to do, optionally by a date.

    Status is derived from the timestamps rather than stored, so a row can
    never disagree with itself.
    """

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Not started'
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        DUE_SOON = 'due_soon', 'Due soon'
        OVERDUE = 'overdue', 'Overdue'
        EXCUSED = 'excused', 'Excused'

    DUE_SOON_WINDOW = timedelta(days=2)

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='practice_assignments')
    practice = models.ForeignKey(
        'practices.Practice', on_delete=models.CASCADE,
        related_name='assignments')
    enrolment = models.ForeignKey(
        Enrolment, on_delete=models.CASCADE, null=True, blank=True,
        related_name='practice_assignments')

    assigned_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    required = models.BooleanField(default=True)
    excused = models.BooleanField(default=False)
    attempt_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['due_at', '-assigned_at']

    def status(self, now=None):
        now = now or timezone.now()
        if self.completed_at is not None:
            return self.Status.COMPLETED
        if self.excused:
            return self.Status.EXCUSED
        if self.due_at is not None:
            if self.due_at < now:
                return self.Status.OVERDUE
            if self.due_at - now <= self.DUE_SOON_WINDOW:
                return self.Status.DUE_SOON
        if self.started_at is not None:
            return self.Status.IN_PROGRESS
        return self.Status.NOT_STARTED

    def __str__(self):
        return f'{self.contact_id} → {self.practice.title}'


class Milestone(models.Model):
    """A progress checkpoint on a programme, e.g. "Complete Level 2"."""

    program = models.ForeignKey(
        'programs.Program', on_delete=models.CASCADE,
        related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    required_progress = models.PositiveSmallIntegerField(
        default=100, help_text='Programme completion %% needed to achieve it.')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'required_progress']

    def status_for(self, percent):
        if percent >= self.required_progress:
            return 'achieved'
        return 'in_progress' if percent > 0 else 'locked'

    def __str__(self):
        return f'{self.title} ({self.required_progress}%)'


class Mentorship(models.Model):
    """The staff member supporting a student, and how they can be reached."""

    student = models.OneToOneField(
        'members.Contact', on_delete=models.CASCADE,
        related_name='mentorship')
    mentor = models.ForeignKey(
        'staff_mgmt.Worker', on_delete=models.CASCADE,
        related_name='mentees')
    availability = models.CharField(
        max_length=255, blank=True,
        help_text='e.g. "Weekdays, 9am - 5pm GMT".')
    next_check_in_at = models.DateTimeField(null=True, blank=True)
    # Messaging and booking are per-programme features, so they are opt-in
    # rather than assumed available.
    messaging_enabled = models.BooleanField(default=False)
    booking_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.student.full_name} ← {self.mentor.contact.full_name}'
