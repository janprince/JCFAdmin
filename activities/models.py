"""
Scheduled activities — the app's Upcoming Activities feed (design 25).

An Activity is a dated happening staff schedule by hand: a live session, a
group practice sitting, or another gathering. The mobile feed merges these
with published Programs (which carry their own dates) into one schedule.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Activity(models.Model):
    class Kind(models.TextChoices):
        LIVE = 'live', 'Live session'
        PRACTICE = 'practice', 'Group practice'
        GATHERING = 'gathering', 'Gathering / other'

    class Audience(models.TextChoices):
        PUBLIC = 'public', 'Public (everyone)'
        MEMBERS = 'members', 'Members & students'
        STUDENTS = 'students', 'Students only'

    class ActivityType(models.TextChoices):
        """What the activity *is* — the badge on the card, and the
        "Activity type" group in the advanced filter sheet. Distinct from
        `kind`, which says how the app opens it."""
        SATSANG = 'satsang', 'Satsang'
        MEDITATION = 'meditation', 'Guided meditation'
        WORKSHOP = 'workshop', 'Workshop'
        TEACHING = 'teaching', 'Teaching'
        RETREAT = 'retreat', 'Retreat'
        PRACTICE = 'practice', 'Group practice'
        COMMUNITY = 'community', 'Community gathering'
        OTHER = 'other', 'Other'

    class Format(models.TextChoices):
        ONLINE = 'online', 'Online'
        IN_PERSON = 'in_person', 'In person'
        HYBRID = 'hybrid', 'Hybrid (both)'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    kind = models.CharField(
        max_length=12, choices=Kind.choices, default=Kind.GATHERING)
    activity_type = models.CharField(
        max_length=16, choices=ActivityType.choices,
        default=ActivityType.OTHER)
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    ends_at = models.DateTimeField(
        null=True, blank=True, editable=False,
        help_text='Derived from starts_at + duration_minutes on save.')
    all_day = models.BooleanField(
        default=False,
        help_text='Show a date without a clock time (retreats, festivals).')

    # --- where ---
    activity_format = models.CharField(
        'format', max_length=12, choices=Format.choices,
        default=Format.IN_PERSON)
    venue = models.CharField(
        max_length=255, blank=True,
        help_text='Physical venue; leave blank for Online.')
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    online_platform = models.CharField(
        max_length=80, blank=True,
        help_text='Zoom, JCF Live, YouTube … shown on online activities.')

    # --- who ---
    facilitator = models.ForeignKey(
        'staff_mgmt.Worker', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activities')
    facilitator_name = models.CharField(
        max_length=255, blank=True,
        help_text='Used when the facilitator is not JCF staff.')
    language = models.CharField(max_length=40, blank=True, default='English')

    # --- artwork ---
    image = models.ImageField(upload_to='activities/', blank=True)
    image_key = models.CharField(
        max_length=64, blank=True,
        help_text='Packaged artwork the app falls back to, e.g. "retreat".')

    # --- registration ---
    registration_required = models.BooleanField(default=False)
    capacity = models.PositiveIntegerField(
        null=True, blank=True, help_text='Blank means unlimited.')
    registration_opens_at = models.DateTimeField(null=True, blank=True)
    registration_closes_at = models.DateTimeField(null=True, blank=True)
    waitlist_enabled = models.BooleanField(default=False)
    fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Blank means free.')
    fee_currency = models.CharField(max_length=3, blank=True, default='GHS')
    external_registration_url = models.URLField(blank=True)

    # --- state ---
    audience = models.CharField(
        max_length=10, choices=Audience.choices, default=Audience.PUBLIC)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(
        default=False,
        help_text='Candidate for the banner above the list. The server picks '
                  'the soonest featured activity the caller may see.')
    featured_blurb = models.CharField(max_length=255, blank=True)
    cancelled = models.BooleanField(default=False)
    rescheduled_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['starts_at']
        verbose_name_plural = 'activities'
        indexes = [
            models.Index(fields=['starts_at', 'id']),
            models.Index(fields=['is_active', 'starts_at']),
            models.Index(fields=['ends_at']),
        ]

    def __str__(self):
        return f'{self.title} @ {self.starts_at:%d %b %Y %H:%M}'

    def save(self, *args, **kwargs):
        # `ends_at` is kept as a real column rather than computed in the
        # query: the feed must keep an activity that is still running, and
        # "starts_at + duration_minutes minutes" is not an expression
        # Postgres and SQLite both accept. A stored, indexed column is one
        # comparison on either backend, and keyset pagination on
        # (starts_at, id) stays intact.
        self.ends_at = self.starts_at + timedelta(
            minutes=self.duration_minutes)
        if (update_fields := kwargs.get('update_fields')) is not None:
            kwargs['update_fields'] = {*update_fields, 'ends_at'}
        super().save(*args, **kwargs)

    @property
    def is_online(self):
        """Hybrid counts as online *and* in person — it genuinely is both,
        so it answers to either filter rather than hiding from one."""
        return self.activity_format in (
            self.Format.ONLINE, self.Format.HYBRID)

    @property
    def is_in_person(self):
        return self.activity_format in (
            self.Format.IN_PERSON, self.Format.HYBRID)

    @property
    def is_free(self):
        return self.fee_amount is None or self.fee_amount <= 0

    def seats_taken(self):
        return self.registrations.filter(
            status=ActivityRegistration.Status.REGISTERED).count()

    def seats_left(self):
        if self.capacity is None:
            return None
        return max(self.capacity - self.seats_taken(), 0)

    def registration_state(self, now=None):
        """Why the caller can or cannot register right now.

        One of: `not_required`, `opens_later`, `open`, `full`, `waitlist`,
        `closed`, `cancelled`, `external`. The app renders the button from
        this string and never recomputes it from the dates.
        """
        now = now or timezone.now()
        if self.cancelled:
            return 'cancelled'
        if not self.registration_required:
            return 'not_required'
        if self.external_registration_url:
            return 'external'
        if self.registration_opens_at and now < self.registration_opens_at:
            return 'opens_later'
        closes = self.registration_closes_at or self.starts_at
        if now >= closes:
            return 'closed'
        left = self.seats_left()
        if left is not None and left <= 0:
            return 'waitlist' if self.waitlist_enabled else 'full'
        return 'open'


class ActivityReminder(models.Model):
    """A member's "remind me" on a feed item — an Activity or a Program.

    Stored server-side now; push delivery rides the FCM track once a
    service account is provisioned.
    """

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='activity_reminders')
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, null=True, blank=True,
        related_name='reminders')
    program = models.ForeignKey(
        'programs.Program', on_delete=models.CASCADE, null=True, blank=True,
        related_name='reminders')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'activity'], name='uniq_activity_reminder',
                condition=models.Q(activity__isnull=False)),
            models.UniqueConstraint(
                fields=['contact', 'program'], name='uniq_program_reminder',
                condition=models.Q(program__isnull=False)),
        ]

    def clean(self):
        if bool(self.activity) == bool(self.program):
            raise ValidationError(
                'A reminder points at exactly one activity or one program.')

    def __str__(self):
        target = self.activity or self.program
        return f'{self.contact_id} → {target}'


class ActivityRegistration(models.Model):
    """A member's place at an activity.

    Separate from a reminder: a reminder is a private nudge, a registration
    takes a seat and staff see it in the dashboard.
    """

    class Status(models.TextChoices):
        REGISTERED = 'registered', 'Registered'
        WAITLISTED = 'waitlisted', 'Waitlisted'
        CANCELLED = 'cancelled', 'Cancelled'

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='activity_registrations')
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name='registrations')
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.REGISTERED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'activity'], name='uniq_activity_signup'),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f'{self.contact_id} → {self.activity_id} ({self.status})'


class ActivitySave(models.Model):
    """A bookmark. Saving is not registering and does not hold a seat."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='activity_saves')
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name='saves')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'activity'], name='uniq_activity_save'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contact_id} saved {self.activity_id}'


# Live streaming models live in their own module for readability.
from .live_models import *  # noqa: E402,F401,F403
