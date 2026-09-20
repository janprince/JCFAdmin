"""
Guided practices + daily practice logging — the InnerSpace practice engine
(design 27): today's practice, streaks, weekly goal, practice library.
"""
from django.db import models
from django.utils.text import slugify

WEEKLY_GOAL = 7  # one practice a day


class Practice(models.Model):
    class Category(models.TextChoices):
        MORNING = 'morning', 'Morning'
        BREATHING = 'breathing', 'Breathing'
        REFLECTION = 'reflection', 'Evening / Reflection'
        GENERAL = 'general', 'General'

    class Audience(models.TextChoices):
        PUBLIC = 'public', 'Public (free intro)'
        MEMBERS = 'members', 'Members & students'
        STUDENTS = 'students', 'Students only'

    title = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=12, choices=Category.choices, default=Category.GENERAL)
    minutes = models.PositiveSmallIntegerField(default=10)
    audience = models.CharField(
        max_length=10, choices=Audience.choices, default=Audience.MEMBERS)
    audio_file = models.FileField(
        upload_to='practices/audio/', blank=True,
        help_text='Guided audio hosted on R2.')
    audio_url = models.URLField(
        blank=True, help_text='External audio URL (used when no file).')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def resolved_audio_url(self):
        if self.audio_file:
            return self.audio_file.url
        return self.audio_url

    def __str__(self):
        return self.title


class PracticeLog(models.Model):
    """One completed practice session on a given day."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='practice_logs')
    practice = models.ForeignKey(
        Practice, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs')
    date = models.DateField()
    minutes = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [models.Index(fields=['contact', 'date'])]

    def __str__(self):
        return f'{self.contact_id} on {self.date}'
