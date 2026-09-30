"""
Engagement: announcements, push device tokens, and in-app notifications.
"""
from math import ceil

from django.db import models
from django.utils.text import slugify


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


class AnnouncementRead(models.Model):
    """A member has opened an announcement — clears its unread dot."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='announcement_reads')
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name='reads')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'announcement'],
                name='uniq_announcement_read'),
        ]

    def __str__(self):
        return f'{self.contact_id} read {self.announcement_id}'


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
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    category = models.CharField(max_length=80, blank=True, default='Awareness')
    title = models.CharField(
        max_length=255, blank=True,
        help_text='Headline for the detail screen; falls back to the quote.')
    quote = models.TextField()
    author = models.CharField(max_length=255, default='Dr. Baffour Jan')
    reflection = models.TextField(
        blank=True, help_text='A short reflection prompt shown under the quote.')
    share_excerpt = models.TextField(
        blank=True,
        help_text='Short line used on share cards; falls back to the quote.')
    hero_image = models.ImageField(upload_to='inspirations/', blank=True)
    hero_alt_text = models.CharField(max_length=255, blank=True)
    prompt_question = models.TextField(
        blank=True, help_text='The "Pause and Reflect" question.')
    prompt_guidance = models.TextField(blank=True)
    audio_file = models.FileField(upload_to='inspirations/audio/', blank=True)
    audio_url = models.URLField(blank=True)
    audio_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    sharing_allowed = models.BooleanField(default=True)
    related_teaching = models.ForeignKey(
        'teachings.Teaching', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inspirations',
        help_text='Optional teaching linked from the inspiration page.')
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title or self.quote)[:200] or 'inspiration'
            self.slug = f'{base}-{self.date:%Y-%m-%d}'
        super().save(*args, **kwargs)

    @property
    def display_title(self):
        return self.title or self.quote

    @property
    def resolved_audio_url(self):
        if self.audio_file:
            return self.audio_file.url
        return self.audio_url

    def reading_time_minutes(self):
        """Rounded up from the body at ~200 words a minute, never below 1."""
        words = len((self.reflection or '').split())
        for block in self.blocks.all():
            words += len((block.text or '').split())
            words += sum(len(str(item).split()) for item in (block.items or []))
        return max(1, ceil(words / 200))

    def __str__(self):
        return f'{self.date}: {self.quote[:40]}'


class InspirationBlock(models.Model):
    """One block of an inspiration's reflection body. Structured rather than
    raw HTML, so the app renders only types it understands."""

    class Kind(models.TextChoices):
        PARAGRAPH = 'paragraph', 'Paragraph'
        HEADING = 'heading', 'Heading'
        SUBHEADING = 'subheading', 'Subheading'
        PULL_QUOTE = 'pull_quote', 'Pull quote'
        IMAGE = 'image', 'Image'
        BULLET_LIST = 'bullet_list', 'Bullet list'
        NUMBERED_LIST = 'numbered_list', 'Numbered list'
        DIVIDER = 'divider', 'Divider'

    inspiration = models.ForeignKey(
        DailyInspiration, on_delete=models.CASCADE, related_name='blocks')
    block_type = models.CharField(
        max_length=16, choices=Kind.choices, default=Kind.PARAGRAPH)
    text = models.TextField(blank=True)
    source = models.CharField(
        max_length=255, blank=True, help_text='Attribution for a pull quote.')
    image = models.ImageField(upload_to='inspirations/body/', blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    items = models.JSONField(
        default=list, blank=True, help_text='List entries, for list blocks.')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.get_block_type_display()} #{self.order}'


class InspirationSave(models.Model):
    """A member has saved an inspiration for later."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='inspiration_saves')
    inspiration = models.ForeignKey(
        DailyInspiration, on_delete=models.CASCADE, related_name='saves')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'inspiration'], name='uniq_inspiration_save'),
        ]


class InspirationReflection(models.Model):
    """A member has marked an inspiration as reflected on."""

    contact = models.ForeignKey(
        'members.Contact', on_delete=models.CASCADE,
        related_name='inspiration_reflections')
    inspiration = models.ForeignKey(
        DailyInspiration, on_delete=models.CASCADE,
        related_name='reflections')
    reflected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'inspiration'],
                name='uniq_inspiration_reflection'),
        ]
