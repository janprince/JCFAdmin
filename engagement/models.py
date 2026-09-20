"""
Engagement: announcements, push device tokens, and in-app notifications.
"""
from django.db import models


class Announcement(models.Model):
    class Audience(models.TextChoices):
        PUBLIC = 'public', 'Public (everyone)'
        MEMBERS = 'members', 'Members & students only'
        STUDENTS = 'students', 'Students only'

    title = models.CharField(max_length=255)
    body = models.TextField()
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.PUBLIC)
    image = models.ImageField(upload_to='announcements/', blank=True)
    is_published = models.BooleanField(default=True)
    pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pinned', '-created_at']

    def __str__(self):
        return self.title


class DeviceToken(models.Model):
    """An FCM registration token for a device. Linked to a Contact if known."""

    class Platform(models.TextChoices):
        IOS = 'ios', 'iOS'
        ANDROID = 'android', 'Android'

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE, null=True, blank=True,
        related_name='device_tokens',
    )
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen_at']

    def __str__(self):
        who = self.contact.full_name if self.contact_id else 'guest'
        return f'{self.platform} token ({who})'


class Notification(models.Model):
    """An in-app notification for a member."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE, related_name='notifications'
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True, help_text='Optional deep-link payload.')
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['contact', 'read_at'])]

    @property
    def is_read(self):
        return self.read_at is not None

    def __str__(self):
        return f'{self.title} -> {self.contact.full_name}'


class DailyInspiration(models.Model):
    """One scheduled quote/teaching per day for the app's Home hero
    (designs 19/22). The app shows the entry for today, falling back to the
    most recent published past entry."""

    date = models.DateField(unique=True, help_text='The day this inspiration is shown.')
    quote = models.TextField()
    author = models.CharField(max_length=255, default='Dr. Baffour Jan')
    reflection = models.TextField(
        blank=True, help_text='A short reflection prompt shown under the quote.')
    related_teaching = models.ForeignKey(
        'teachings.Teaching', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inspirations',
        help_text='Optional teaching linked from the inspiration page.')
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.date}: {self.quote[:40]}'
