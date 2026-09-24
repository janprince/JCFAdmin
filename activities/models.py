"""
Scheduled activities — the app's Upcoming Activities feed (design 25).

An Activity is a dated happening staff schedule by hand: a live session, a
group practice sitting, or another gathering. The mobile feed merges these
with published Programs (which carry their own dates) into one schedule.
"""
from django.core.exceptions import ValidationError
from django.db import models


class Activity(models.Model):
    class Kind(models.TextChoices):
        LIVE = 'live', 'Live session'
        PRACTICE = 'practice', 'Group practice'
        GATHERING = 'gathering', 'Gathering / other'

    class Audience(models.TextChoices):
        PUBLIC = 'public', 'Public (everyone)'
        MEMBERS = 'members', 'Members & students'
        STUDENTS = 'students', 'Students only'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    kind = models.CharField(
        max_length=12, choices=Kind.choices, default=Kind.GATHERING)
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    venue = models.CharField(
        max_length=255, blank=True,
        help_text='Physical venue; leave blank for Online.')
    audience = models.CharField(
        max_length=10, choices=Audience.choices, default=Audience.PUBLIC)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['starts_at']
        verbose_name_plural = 'activities'

    def __str__(self):
        return f'{self.title} @ {self.starts_at:%d %b %Y %H:%M}'


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
