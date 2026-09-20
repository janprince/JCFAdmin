from django.db import models
from django.utils.text import slugify


class TeachingSeries(models.Model):
    """A grouping of teachings (e.g. an InnerSpace course or lecture series)."""

    title = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to='teachings/series/', blank=True)
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers appear first.')
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'teaching series'
        ordering = ['order', 'title']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Teaching(models.Model):
    class Format(models.TextChoices):
        LECTURE = 'lecture', 'Lecture'
        INTERVIEW = 'interview', 'Interview'
        LIVE = 'live', 'Live'
        DOCUMENTARY = 'documentary', 'Documentary'
        PROMOTIONAL = 'promotional', 'Promotional'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ARCHIVE = 'archive', 'Archive'
        PUBLISHED = 'published', 'Published'

    class Language(models.TextChoices):
        ENGLISH = 'english', 'English'
        TWI = 'twi', 'Twi'

    class Tier(models.TextChoices):
        GENERAL = 'general', 'General (open to everyone)'
        PREMIUM = 'premium', 'Premium (members/students only)'

    class MediaKind(models.TextChoices):
        VIDEO = 'video', 'Video'
        AUDIO = 'audio', 'Audio'

    topic = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    author = models.CharField(
        max_length=255, default='Dr. Baffour Jan',
        help_text='Shown as the teaching attribution in the app.')
    format = models.CharField(max_length=50, choices=Format.choices, default=Format.LECTURE)
    language = models.CharField(max_length=50, choices=Language.choices, default=Language.ENGLISH)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
    description = models.TextField(blank=True)

    # Access tier — premium content is gated to members/students.
    tier = models.CharField(max_length=10, choices=Tier.choices, default=Tier.GENERAL)

    # Grouping
    series = models.ForeignKey(
        TeachingSeries, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teachings',
    )
    order = models.PositiveIntegerField(default=0, help_text='Order within a series.')

    # Media — supports BOTH a YouTube link and/or an R2-hosted file.
    media_kind = models.CharField(max_length=10, choices=MediaKind.choices, default=MediaKind.VIDEO)
    youtube_url = models.URLField(blank=True, help_text='YouTube URL, if hosted on YouTube.')
    media_file = models.FileField(upload_to='teachings/media/', blank=True,
                                  help_text='Video/audio file hosted on R2.')
    thumbnail = models.ImageField(upload_to='teachings/thumbs/', blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    view_count = models.PositiveIntegerField(
        default=0, help_text='Times the teaching was opened in the app.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.topic)
        super().save(*args, **kwargs)

    @property
    def is_premium(self):
        return self.tier == self.Tier.PREMIUM

    @property
    def media_url(self):
        """Public R2 URL for the uploaded media file, if any."""
        if self.media_file:
            return self.media_file.url
        return ''

    def __str__(self):
        return self.topic


class TeachingProgress(models.Model):
    """A member's position in a teaching — powers Continue Learning
    (design 26). Rows are created on first open; completion is an explicit
    member action until the in-app player reports playback position."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='teaching_progress')
    teaching = models.ForeignKey(
        Teaching, on_delete=models.CASCADE, related_name='progress_rows')
    percent = models.PositiveSmallIntegerField(default=0)
    position_seconds = models.PositiveIntegerField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    last_viewed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_viewed_at']
        verbose_name_plural = 'teaching progress'
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'teaching'], name='unique_contact_teaching'),
        ]

    def __str__(self):
        return f'{self.contact_id} -> {self.teaching.topic}: {self.percent}%'
