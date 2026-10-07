from urllib.parse import urlsplit

from django.db import models


class DigitalResource(models.Model):
    """A Foundation web platform, page or playlist the office shares often."""
    class Category(models.TextChoices):
        PLATFORM = 'platform', 'Platforms & websites'
        LESSONS = 'lessons', 'Lessons & courses'
        MEDIA = 'media', 'Social media & channels'
        FORMS = 'forms', 'Forms & tools'
        OTHER = 'other', 'Other'

    class Audience(models.TextChoices):
        EVERYONE = 'everyone', 'Everyone'
        STUDENTS = 'students', 'Students'
        MEMBERS = 'members', 'Members'
        STAFF = 'staff', 'Service team'

    title = models.CharField(max_length=120)
    url = models.URLField('Link', max_length=500)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.PLATFORM)
    audience = models.CharField('Who uses it', max_length=20, choices=Audience.choices, default=Audience.EVERYONE)
    language = models.CharField(max_length=40, blank=True, help_text='Only if the content is in one language, e.g. English or Twi.')
    description = models.CharField(max_length=255, blank=True, help_text='One line on what it is or when to share it.')
    share_privately = models.BooleanField('Share only with its audience', default=False,
                                          help_text='For unlisted lessons and private links. Shown as a reminder beside the link.')
    position = models.PositiveSmallIntegerField(default=0, help_text='Lower numbers appear first within their group.')
    is_active = models.BooleanField('Show on the resources page', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'title']

    def __str__(self):
        return self.title

    @property
    def display_url(self):
        """The link as people say it: no scheme, no trailing slash."""
        parts = urlsplit(self.url)
        text = parts.netloc + parts.path.rstrip('/')
        if parts.query:
            text += '?' + parts.query
        return text
